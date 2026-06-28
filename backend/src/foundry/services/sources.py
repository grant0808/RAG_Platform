from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.config import Settings
from foundry.core.errors import NotFoundError, ValidationError
from foundry.models import Source
from foundry.services.knowledge import KnowledgeIndex
from foundry.services.tables import TableStore, safe_identifier

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".html", ".pdf", ".csv", ".xlsx", ".xlsm"}


class SourceService:
    def __init__(
        self,
        settings: Settings,
        knowledge: KnowledgeIndex,
        tables: TableStore,
    ) -> None:
        self.settings = settings
        self.knowledge = knowledge
        self.tables = tables
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
        await asyncio.to_thread(path.write_bytes, payload)
        source.path = str(path)

        documents: list[Document]
        if suffix in {".csv", ".xlsx", ".xlsm"}:
            source.table_name = f"source_{safe_identifier(source.id)}"
            await asyncio.to_thread(self.tables.import_file, path, source.table_name)
            content = await asyncio.to_thread(self.tables.catalog_text, source.table_name)
            documents = [self._document(source, content, "table_catalog")]
        else:
            content = await asyncio.to_thread(self._extract_text, path, payload, suffix)
            documents = self._split_documents(source, content)

        source.chunk_count = self.knowledge.add_documents(documents)
        source.status = "ready"
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
        result = await session.execute(select(Source).where(Source.status == "ready"))
        for source in result.scalars():
            path = Path(source.path)
            if not await asyncio.to_thread(path.exists):
                continue
            suffix = path.suffix.lower()
            if source.table_name:
                try:
                    await asyncio.to_thread(self.tables.import_file, path, source.table_name)
                    content = await asyncio.to_thread(self.tables.catalog_text, source.table_name)
                    self.knowledge.add_documents([self._document(source, content, "table_catalog")])
                except Exception:
                    continue
            else:
                payload = await asyncio.to_thread(path.read_bytes)
                content = await asyncio.to_thread(self._extract_text, path, payload, suffix)
                self.knowledge.add_documents(self._split_documents(source, content))

    def _split_documents(self, source: Source, content: str) -> list[Document]:
        if not content.strip():
            raise ValidationError("No text could be extracted from the file")
        base = self._document(source, content, "document")
        documents = self.splitter.split_documents([base])
        originals = [document.page_content for document in documents]
        document_context = self._contextual_summary(source, content)
        for index, document in enumerate(documents):
            original_text = originals[index]
            before = originals[index - 1] if index > 0 else ""
            after = originals[index + 1] if index + 1 < len(originals) else ""
            document.metadata["chunk_index"] = index
            document.metadata["location"] = f"chunk:{index}"
            document.metadata["original_text"] = original_text
            document.metadata["late_context_before"] = self._snippet(before)
            document.metadata["late_context_after"] = self._snippet(after)
            document.metadata["contextual_summary"] = document_context
            document.page_content = (
                f"Document: {source.name}\n"
                f"Context: {document_context}\n"
                f"Chunk {index + 1} of {len(documents)}:\n{original_text}"
            )
        return documents

    @staticmethod
    def _document(source: Source, content: str, location: str) -> Document:
        return Document(
            page_content=content,
            metadata={
                "source_id": source.id,
                "source_name": source.name,
                "source_kind": source.kind,
                "location": location,
            },
        )

    @staticmethod
    def _contextual_summary(source: Source, content: str) -> str:
        compact = " ".join(content.split())
        return f"{source.kind} source named {source.name}. Leading context: {compact[:500]}"

    @staticmethod
    def _snippet(text: str, limit: int = 600) -> str:
        compact = " ".join(text.split())
        return compact[:limit]

    @staticmethod
    def _kind_for(suffix: str) -> str:
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".csv", ".xlsx", ".xlsm"}:
            return "table"
        return "document"

    @staticmethod
    def _extract_text(path: Path, payload: bytes, suffix: str) -> str:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(payload))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        text = payload.decode("utf-8", errors="replace")
        if suffix == ".json":
            try:
                return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON file: {path.name}") from exc
        return text
