from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.config import Settings
from foundry.core.errors import ConfigurationError, NotFoundError, ValidationError
from foundry.models import Source
from foundry.services.knowledge import KnowledgeIndex

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".html", ".pdf"}
PYPDF_LOGGERS = ("pypdf", "pypdf._reader", "pypdf.generic._image_inline")
NO_TEXT_STATUS = "no_text"
READY_STATUS = "ready"
PAPER_DOCUMENT_TYPE = "ai_computer_science_paper"
SUPPORTED_PDF_PARSERS = {"docling", "pypdf"}


@dataclass(frozen=True)
class ExtractedDocument:
    content: str
    metadata: dict[str, str | int | float | bool]
    location: str = "document"
    pre_chunked: bool = False


class SourceService:
    def __init__(
        self,
        settings: Settings,
        knowledge: KnowledgeIndex,
    ) -> None:
        self.settings = settings
        self.knowledge = knowledge
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    async def ingest(self, session: AsyncSession, upload: UploadFile) -> Source:
        filename = Path(upload.filename or "upload").name
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValidationError(f"Unsupported file type: {suffix or 'unknown'}")
        payload = await upload.read(self.settings.max_upload_bytes + 1)
        if len(payload) > self.settings.max_upload_bytes:
            raise ValidationError("Uploaded file exceeds the size limit")
        if not payload:
            raise ValidationError("Uploaded file is empty")

        source = Source(
            name=filename,
            kind=self._kind_for(suffix),
            path="pending",
            size_bytes=len(payload),
        )
        session.add(source)
        await session.flush()
        path = self.settings.data_dir / "uploads" / f"{source.id}{suffix}"
        try:
            await asyncio.to_thread(path.write_bytes, payload)
            source.path = str(path)

            extracted = await asyncio.to_thread(
                self._extract_documents,
                source,
                path,
                payload,
                suffix,
            )
            documents = self._split_documents(source, extracted, allow_empty=suffix == ".pdf")

            source.chunk_count = self._index_documents(documents) if documents else 0
            source.status = READY_STATUS if documents else NO_TEXT_STATUS
        except ValidationError:
            await self._cleanup_failed_ingest(path, source.table_name)
            raise
        except ConfigurationError:
            await self._cleanup_failed_ingest(path, source.table_name)
            raise
        except OSError as exc:
            await self._cleanup_failed_ingest(path, source.table_name)
            raise ConfigurationError("Upload storage is unavailable") from exc
        except Exception as exc:
            await self._cleanup_failed_ingest(path, source.table_name)
            raise ValidationError(
                f"Failed to process uploaded file. Ensure {filename} is a valid {suffix} file."
            ) from exc
        await session.flush()
        await session.refresh(source)
        return source

    async def list(self, session: AsyncSession) -> list[Source]:
        result = await session.execute(select(Source).order_by(Source.created_at.desc()))
        return list(result.scalars())

    async def get(self, session: AsyncSession, source_id: str) -> Source:
        source = await session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")
        return source

    async def delete(self, session: AsyncSession, source_id: str) -> None:
        source = await self.get(session, source_id)
        path = Path(source.path)
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)
        await session.delete(source)
        await session.flush()
        await self.rebuild(session)

    async def rebuild(self, session: AsyncSession) -> None:
        self.knowledge.reset()
        result = await session.execute(select(Source).where(Source.status == READY_STATUS))
        for source in result.scalars():
            path = Path(source.path)
            if not await asyncio.to_thread(path.exists):
                continue
            suffix = path.suffix.lower()
            payload = await asyncio.to_thread(path.read_bytes)
            extracted = await asyncio.to_thread(
                self._extract_documents,
                source,
                path,
                payload,
                suffix,
            )
            self.knowledge.add_documents(
                self._split_documents(source, extracted, allow_empty=False)
            )

    def _split_documents(
        self,
        source: Source,
        extracted_documents: list[ExtractedDocument],
        *,
        allow_empty: bool = False,
    ) -> list[Document]:
        documents = [
            self._document(source, item.content, item.location, item.metadata)
            for item in extracted_documents
            if item.pre_chunked and item.content.strip()
        ]
        base_documents = [
            self._document(source, item.content, item.location, item.metadata)
            for item in extracted_documents
            if not item.pre_chunked and item.content.strip()
        ]
        if not base_documents and not documents:
            if allow_empty:
                return []
            raise ValidationError("No text could be extracted from the file")
        split_documents = self.splitter.split_documents(base_documents) if base_documents else []
        originals = [document.page_content for document in split_documents]
        document_context = self._contextual_summary(
            source,
            "\n\n".join(document.page_content for document in base_documents or documents),
            (base_documents or documents)[0].metadata,
        )
        for index, document in enumerate(split_documents):
            original_text = originals[index]
            before = originals[index - 1] if index > 0 else ""
            after = originals[index + 1] if index + 1 < len(originals) else ""
            document.metadata["chunk_index"] = index
            document.metadata["chunk_count"] = len(split_documents)
            document.metadata["location"] = self._chunk_location(document.metadata, index)
            document.metadata["original_text"] = original_text
            document.metadata["late_context_before"] = self._snippet(before)
            document.metadata["late_context_after"] = self._snippet(after)
            document.metadata["contextual_summary"] = document_context
            document.page_content = (
                f"Document: {source.name}\n"
                f"Context: {document_context}\n"
                f"Chunk {index + 1} of {len(split_documents)}:\n{original_text}"
            )
        documents.extend(split_documents)
        for index, document in enumerate(documents):
            document.metadata["chunk_index"] = index
            document.metadata["chunk_count"] = len(documents)
        return documents

    @staticmethod
    def _document(
        source: Source,
        content: str,
        location: str,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> Document:
        document_metadata: dict[str, str | int | float | bool] = {
            "source_id": source.id,
            "source_name": source.name,
            "source_kind": source.kind,
            "location": location,
        }
        if metadata:
            document_metadata.update(metadata)
        return Document(
            page_content=content,
            metadata=document_metadata,
        )

    @staticmethod
    def _contextual_summary(
        source: Source,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> str:
        compact = " ".join(content.split())
        title = str((metadata or {}).get("title") or source.name)
        document_type = str((metadata or {}).get("document_type") or source.kind)
        parser = str((metadata or {}).get("parser") or "plain-text")
        return (
            f"{document_type} source named {title} parsed by {parser}. "
            f"Leading context: {compact[:500]}"
        )

    @staticmethod
    def _snippet(text: str, limit: int = 600) -> str:
        compact = " ".join(text.split())
        return compact[:limit]

    @staticmethod
    def _kind_for(suffix: str) -> str:
        if suffix == ".pdf":
            return "pdf"
        return "document"

    async def _cleanup_failed_ingest(self, path: Path, table_name: str | None) -> None:
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)

    def _index_documents(self, documents: list[Document]) -> int:
        try:
            return self.knowledge.add_documents(documents)
        except ConfigurationError:
            raise
        except Exception as exc:
            raise ConfigurationError(
                "Knowledge index is unavailable. Check embedding/vector store configuration."
            ) from exc

    def _extract_documents(
        self,
        source: Source,
        path: Path,
        payload: bytes,
        suffix: str,
    ) -> list[ExtractedDocument]:
        if suffix == ".pdf":
            return self._extract_pdf_documents(source, path, payload)
        text = payload.decode("utf-8", errors="replace")
        if suffix == ".json":
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON file: {path.name}") from exc
        return [
            ExtractedDocument(
                content=text,
                metadata={
                    "parser": "plain-text",
                    "document_type": "document",
                    "file_extension": suffix,
                },
            )
        ]

    def _extract_pdf_documents(
        self,
        source: Source,
        path: Path,
        payload: bytes,
    ) -> list[ExtractedDocument]:
        parser = self.settings.pdf_parser.lower()
        if parser not in SUPPORTED_PDF_PARSERS:
            raise ConfigurationError(
                f"Unsupported PDF parser: {self.settings.pdf_parser}. "
                "Supported values: 'docling', 'pypdf'."
            )
        if parser == "docling":
            return self._extract_pdf_with_docling(source, path)
        text = self._extract_pdf_with_pypdf(path, payload)
        if not text.strip():
            return []
        return [
            ExtractedDocument(
                content=text,
                metadata={
                    "parser": "pypdf",
                    "document_type": PAPER_DOCUMENT_TYPE,
                    "file_extension": ".pdf",
                    "title": source.name,
                    "normalized_format": "plain_text",
                },
            )
        ]

    def _extract_pdf_with_docling(self, source: Source, path: Path) -> list[ExtractedDocument]:
        try:
            from docling.chunking import HybridChunker
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ConfigurationError(
                "Docling PDF parsing requires the docling package. "
                "Run `uv sync` after updating dependencies."
            ) from exc

        try:
            result = DocumentConverter().convert(source=path)
            document = result.document
        except Exception as exc:
            raise ValidationError(f"Docling PDF parsing failed: {path.name}") from exc

        chunker = self._docling_chunker(HybridChunker)
        try:
            chunks = list(chunker.chunk(dl_doc=document))
        except Exception as exc:
            raise ValidationError(f"Docling PDF chunking failed: {path.name}") from exc

        if not chunks:
            content = self._docling_text(document)
            if not content.strip():
                return []
            return [
                ExtractedDocument(
                    content=content,
                    metadata=self._docling_document_metadata(source, document, path, content),
                )
            ]

        extracted: list[ExtractedDocument] = []
        original_texts = [str(getattr(chunk, "text", "")) for chunk in chunks]
        for index, chunk in enumerate(chunks):
            original_text = original_texts[index].strip()
            if not original_text:
                continue
            content = str(chunker.contextualize(chunk=chunk)).strip() or original_text
            metadata = self._docling_chunk_metadata(
                source=source,
                path=path,
                document=document,
                chunk=chunk,
                index=index,
                total_chunks=len(chunks),
                content=content,
            )
            before = original_texts[index - 1] if index > 0 else ""
            after = original_texts[index + 1] if index + 1 < len(original_texts) else ""
            metadata["original_text"] = original_text
            metadata["late_context_before"] = self._snippet(before)
            metadata["late_context_after"] = self._snippet(after)
            metadata["contextual_summary"] = self._contextual_summary(source, content, metadata)
            extracted.append(
                ExtractedDocument(
                    content=content,
                    metadata=metadata,
                    location=str(metadata["location"]),
                    pre_chunked=True,
                )
            )
        if not extracted:
            return []
        return extracted

    def _docling_chunker(self, hybrid_chunker_cls: type[Any]) -> Any:
        try:
            from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
            from transformers import AutoTokenizer

            tokenizer = HuggingFaceTokenizer(
                tokenizer=AutoTokenizer.from_pretrained(self.settings.huggingface_embedding_model),
                max_tokens=self.settings.docling_chunker_max_tokens,
            )
            return hybrid_chunker_cls(
                tokenizer=tokenizer,
                merge_peers=self.settings.docling_chunker_merge_peers,
            )
        except Exception:
            logging.getLogger("foundry").info(
                "Docling Hugging Face tokenizer is unavailable; using default HybridChunker",
            )
            return hybrid_chunker_cls(merge_peers=self.settings.docling_chunker_merge_peers)

    def _docling_chunk_metadata(
        self,
        *,
        source: Source,
        path: Path,
        document: object,
        chunk: object,
        index: int,
        total_chunks: int,
        content: str,
    ) -> dict[str, str | int | float | bool]:
        metadata = self._docling_document_metadata(source, document, path, content)
        metadata["location"] = f"docling_chunk:{index}"
        metadata["chunk_index"] = index
        metadata["chunk_count"] = total_chunks
        chunk_meta = getattr(chunk, "meta", None)
        if chunk_meta is None:
            return metadata

        headings = self._string_list(getattr(chunk_meta, "headings", None))
        captions = self._string_list(getattr(chunk_meta, "captions", None))
        labels = self._docling_labels(chunk_meta)
        pages = self._docling_pages(chunk_meta)
        if headings:
            metadata["section_path"] = " > ".join(headings)
        if captions:
            metadata["captions"] = " | ".join(captions)
        if labels:
            metadata["docling_labels"] = ",".join(labels)
        if pages:
            metadata["page_start"] = min(pages)
            metadata["page_end"] = max(pages)
        return metadata

    @staticmethod
    def _docling_text(document: object) -> str:
        if hasattr(document, "export_to_markdown"):
            return str(document.export_to_markdown())
        if hasattr(document, "export_to_text"):
            return str(document.export_to_text())
        return str(document)

    @staticmethod
    def _docling_document_metadata(
        source: Source,
        document: object,
        path: Path,
        content: str,
    ) -> dict[str, str | int | float | bool]:
        headings = [
            line.strip("# ").strip()
            for line in content.splitlines()
            if line.lstrip().startswith("#") and line.strip("# ").strip()
        ]
        pages = getattr(document, "pages", None)
        metadata: dict[str, str | int | float | bool] = {
            "parser": "docling",
            "document_type": PAPER_DOCUMENT_TYPE,
            "file_extension": path.suffix.lower(),
            "normalized_format": "markdown",
            "title": str(getattr(document, "name", None) or source.name),
        }
        if pages is not None:
            try:
                metadata["page_count"] = len(pages)
            except TypeError:
                pass
        if headings:
            metadata["headings"] = " | ".join(headings[:20])
        return metadata

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list | tuple | set):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    @staticmethod
    def _docling_pages(chunk_meta: object) -> list[int]:
        pages: set[int] = set()
        for item in getattr(chunk_meta, "doc_items", []) or []:
            for provenance in getattr(item, "prov", []) or []:
                page_no = getattr(provenance, "page_no", None)
                if isinstance(page_no, int):
                    pages.add(page_no)
        return sorted(pages)

    @staticmethod
    def _docling_labels(chunk_meta: object) -> list[str]:
        labels: set[str] = set()
        for item in getattr(chunk_meta, "doc_items", []) or []:
            label = getattr(item, "label", None)
            if label is not None:
                labels.add(str(label))
        return sorted(labels)

    @staticmethod
    def _extract_pdf_with_pypdf(path: Path, payload: bytes) -> str:
        previous_levels = [
            (logger := logging.getLogger(name), logger.level) for name in PYPDF_LOGGERS
        ]
        try:
            for logger, _level in previous_levels:
                logger.setLevel(logging.CRITICAL + 1)
            try:
                reader = PdfReader(BytesIO(payload))
                page_texts = [page.extract_text() or "" for page in reader.pages]
            except PdfReadError as exc:
                raise ValidationError(f"Invalid PDF file: {path.name}") from exc
            except Exception as exc:
                raise ValidationError(f"PDF text extraction failed: {path.name}") from exc
            return "\n\n".join(page_texts)
        finally:
            for logger, level in previous_levels:
                logger.setLevel(level)

    @staticmethod
    def _chunk_location(metadata: dict[str, object], index: int) -> str:
        page = metadata.get("page")
        if page is not None:
            return f"page:{page}:chunk:{index}"
        section = metadata.get("section")
        if section:
            return f"section:{section}:chunk:{index}"
        return f"chunk:{index}"
