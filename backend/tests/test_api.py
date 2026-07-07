import sys
from io import BytesIO
from types import ModuleType, SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk
from pypdf import PdfWriter

from foundry.core.config import Settings
from foundry.main import create_app
from foundry.services.knowledge import KnowledgeIndex, LocalHashEmbeddings

PDF_WITH_TEXT = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
    b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
    b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"5 0 obj<</Length 44>>stream\n"
    b"BT /F1 24 Tf 72 720 Td (Hello PDF upload) Tj ET\n"
    b"endstream endobj\n"
    b"xref\n"
    b"0 6\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"0000000241 00000 n \n"
    b"0000000311 00000 n \n"
    b"trailer<</Size 6/Root 1 0 R>>\n"
    b"startxref\n"
    b"405\n"
    b"%%EOF\n"
)


class FakeChatModel:
    seen_messages = []

    async def ainvoke(self, messages):
        type(self).seen_messages.append(messages)
        return AIMessage(
            content="Atlas Pro가 가장 많은 문의를 받았습니다.",
            usage_metadata={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        )

    async def astream(self, messages):
        type(self).seen_messages.append(messages)
        yield AIMessageChunk(content="Atlas Pro")
        yield AIMessageChunk(
            content="가 가장 많습니다.",
            usage_metadata={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        )


class FailingStreamModel:
    async def astream(self, _messages):
        raise RuntimeError("model unavailable")
        yield


class QuotaLimitedModel:
    async def ainvoke(self, _messages):
        raise RuntimeError("Error code: 429 - insufficient_quota")

    async def astream(self, _messages):
        raise RuntimeError("Error code: 429 - insufficient_quota")
        yield


def connect_provider(client):
    response = client.put(
        "/api/v1/providers/openai",
        json={"api_key": "sk-test-super-secret", "validate_connection": False},
    )
    assert response.status_code == 200
    return response


def create_pipeline(client, strategy="rag"):
    response = client.post(
        "/api/v1/pipelines",
        json={
            "name": f"{strategy.upper()} assistant",
            "strategy": strategy,
            "provider": "openai",
            "model": "gpt-test",
            "top_k": 5,
            "similarity_threshold": 0,
        },
    )
    assert response.status_code == 201
    return response.json()


def install_fake_model(app, monkeypatch):
    FakeChatModel.seen_messages = []

    async def fake_model(*_args, **_kwargs):
        return FakeChatModel()

    monkeypatch.setattr(app.state.container.orchestrator, "_model", fake_model)


def test_health_explicitly_reports_auth_disabled(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["auth_enabled"] is False


def test_provider_key_is_masked_and_never_returned(client):
    response = connect_provider(client)
    body = response.json()

    assert body["masked_key"].endswith("cret")
    assert "sk-test-super-secret" not in response.text
    listed = client.get("/api/v1/providers")
    assert "sk-test-super-secret" not in listed.text


def test_openai_provider_key_is_used_for_embeddings(client, app):
    connect_provider(client)

    settings = app.state.container.settings
    assert settings.openai_api_key is not None
    assert settings.openai_embedding_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-test-super-secret"
    assert settings.openai_embedding_api_key.get_secret_value() == "sk-test-super-secret"

    response = client.delete("/api/v1/providers/openai")
    assert response.status_code == 204
    assert settings.openai_api_key is None
    assert settings.openai_embedding_api_key is None


def test_pipeline_default_model_is_openai_chat_default(client):
    connect_provider(client)

    response = client.post(
        "/api/v1/pipelines",
        json={"name": "Default model RAG", "strategy": "rag", "provider": "openai"},
    )

    assert response.status_code == 201
    assert response.json()["model"] == "gpt-4o-mini"


def test_startup_rewrites_invalid_openai_pipeline_models(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    common_settings = {
        "data_dir": tmp_path / "data",
        "database_url": database_url,
        "vector_store_provider": "memory",
        "embedding_provider": "local",
        "pdf_parser": "pypdf",
        "openai_api_key": None,
        "openai_embedding_api_key": None,
        "openai_admin_api_key": None,
        "master_key_path": tmp_path / "master.key",
        "cors_origins": ["http://testserver"],
    }
    fake_settings = Settings(fake_llm_enabled=True, **common_settings)
    with TestClient(create_app(fake_settings)) as first_client:
        connect_provider(first_client)
        response = first_client.post(
            "/api/v1/pipelines",
            json={
                "name": "Old local model",
                "strategy": "rag",
                "provider": "openai",
                "model": "gpt-local-demo",
            },
        )
        assert response.status_code == 201

    real_settings = Settings(fake_llm_enabled=False, **common_settings)
    with TestClient(create_app(real_settings)) as second_client:
        pipelines = second_client.get("/api/v1/pipelines").json()

    assert pipelines[0]["model"] == "gpt-4o-mini"


def test_ollama_provider_can_connect_with_default_base_url(client):
    response = client.put(
        "/api/v1/providers/ollama",
        json={"api_key": "", "validate_connection": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["masked_key"].endswith("1434")
    assert body["models"] == []

    pipeline = client.post(
        "/api/v1/pipelines",
        json={
            "name": "Ollama RAG",
            "strategy": "rag",
            "provider": "ollama",
            "model": "llama3.1",
            "similarity_threshold": 0,
        },
    )
    assert pipeline.status_code == 201
    assert pipeline.json()["provider"] == "ollama"


def test_source_pipeline_version_and_rag_chat(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    upload = client.post(
        "/api/v1/sources/upload",
        files={"file": ("handbook.md", "Atlas Pro support handbook and warranty policy.")},
    )
    assert upload.status_code == 201
    assert upload.json()["chunk_count"] >= 1

    pipeline = create_pipeline(client, "rag")
    version = client.post(f"/api/v1/pipelines/{pipeline['id']}/versions")
    assert version.status_code == 201
    assert version.json()["version"] == 2

    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "Atlas Pro 정책은?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "rag"
    assert body["citations"][0]["source_name"] == "handbook.md"
    assert any(event["step"] == "retriever" for event in body["trace"])


def test_general_question_skips_rag_route(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "안녕, 간단히 인사해줘"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "general"
    assert body["contexts"] == []
    assert body["citations"] == []
    assert any(event["step"] == "rag_router" for event in body["trace"])


def test_web_fallback_route_uses_dummy_provider(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "최신 RAG 논문 동향을 웹에서 찾아줘"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "web_fallback"
    assert body["sources"][0]["type"] == "web"
    assert body["sources"][0]["provider"] == "dummy"
    assert any(event["step"] == "web_search" for event in body["trace"])


def test_chat_routes_general_questions_without_retrieval(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/chat/query",
        json={"pipeline_id": pipeline["id"], "message": "안녕, 오늘 테스트 상태를 알려줘"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "general"
    assert body["citations"] == []
    assert not any(event["step"] == "retriever" for event in body["trace"])


def test_langgraph_rag_route_selects_keyword_tool_for_exact_terms(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("paper.md", "BERT fine-tuning experiment Table 2 accuracy result.")},
    )
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/rag/query",
        json={"pipeline_id": pipeline["id"], "message": "논문에서 BERT Table 2 결과는?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] in {"rag", "web_fallback"}
    assert body["selected_tool"] == "keyword_search_healthcare_pdf"
    assert body["rewritten_query"]
    assert any(event["step"] == "rewrite_query" for event in body["trace"])


def test_langgraph_rag_route_selects_vector_tool_for_definition(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={
            "file": (
                "paper.md",
                "Retrieval augmented generation combines search and generation.",
            )
        },
    )
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/rag/query",
        json={"pipeline_id": pipeline["id"], "message": "문서에서 RAG 개념을 설명해줘"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_tool"] == "vector_search_healthcare_pdf"
    assert any(event["step"] == "select_retrieval_tool" for event in body["trace"])


def test_langgraph_rag_route_uses_duckduckgo_fallback_when_context_missing(
    client,
    app,
    monkeypatch,
):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/rag/query",
        json={"pipeline_id": pipeline["id"], "message": "업로드한 논문에서 없는 실험 결과는?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "web_fallback"
    assert body["web_results"]
    assert body["sources"][0]["type"] == "web"
    assert any(event["step"] == "web_search_fallback" for event in body["trace"])


def test_chat_uses_dummy_web_fallback_when_rag_context_is_missing(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "업로드한 논문에서 모델 한계는?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "web_fallback"
    assert body["sources"][0]["type"] == "web"
    assert body["citations"][0]["provider"] == "dummy"
    assert any(event["step"] == "web_search" for event in body["trace"])


def test_langgraph_rag_query_routes_general_without_retrieval(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/rag/query",
        json={"pipeline_id": pipeline["id"], "message": "안녕, 간단히 인사해줘"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "general"
    assert body["selected_tool"] == "none"
    assert body["contexts"] == []
    assert any(event["step"] == "route_question" for event in body["trace"])


def test_langgraph_rag_query_uses_hybrid_tool_and_reranker(client, app, monkeypatch):
    app.state.container.settings.min_context_count = 1
    app.state.container.settings.rerank_score_threshold = 0
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    upload = client.post(
        "/api/v1/sources/upload",
        files={
            "file": (
                "paper.md",
                "Transformer method improves attention experiment result. "
                "The limitation is compute cost.",
            )
        },
    )
    assert upload.status_code == 201
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/rag/query",
        json={"pipeline_id": pipeline["id"], "message": "논문에서 method와 result를 비교해줘"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "rag"
    assert body["selected_tool"] == "hybrid_search_healthcare_pdf"
    assert body["rewritten_query"]
    assert body["contexts"]
    assert body["contexts"][0]["rerank_score"] >= 0
    assert body["reranker_model"] == "BAAI/bge-reranker-v2-m3"
    assert any(event["step"] == "rerank_documents" for event in body["trace"])


def test_langgraph_rag_query_falls_back_to_web_when_context_missing(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/rag/query",
        json={
            "pipeline_id": pipeline["id"],
            "message": "업로드한 PDF에서 unknown method 한계를 찾아줘",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "web_fallback"
    assert body["sources"][0]["type"] == "web"
    assert body["web_results"][0]["provider"] == "dummy"
    assert any(event["step"] == "web_search_fallback" for event in body["trace"])


def test_retrieval_tool_selector_prefers_keyword_vector_and_hybrid(client, app):
    tools = app.state.container.langgraph_workflow.retrieval_tools

    assert (
        tools.select_tool(
            rewritten_query="BERT dataset table 2",
            search_intent="general",
            keywords=["bert", "dataset"],
        )
        == "keyword_search_healthcare_pdf"
    )
    assert (
        tools.select_tool(
            rewritten_query="attention mechanism concept",
            search_intent="definition",
            keywords=["attention", "mechanism"],
        )
        == "vector_search_healthcare_pdf"
    )
    assert (
        tools.select_tool(
            rewritten_query="method experiment result comparison",
            search_intent="comparison",
            keywords=["method", "experiment", "result"],
        )
        == "hybrid_search_healthcare_pdf"
    )


def test_ragas_evaluation_endpoint_persists_json_result(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/evaluations/ragas",
        json={
            "pipeline_id": pipeline["id"],
            "run_name": "smoke",
            "dataset": [
                {
                    "question": "업로드한 논문에서 Atlas Pro 정책은?",
                    "ground_truth": "Atlas Pro support handbook and warranty policy.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_name"] == "smoke"
    assert body["ragas_backend"] in {"proxy", "ragas-installed-proxy-runner"}
    assert body["averages"].keys() >= {
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    }
    assert (app.state.container.settings.ragas_results_dir / f"{body['id']}.json").exists()


def test_invalid_upload_returns_validation_error(client):
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("broken.pdf", b"this is not a valid pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert client.get("/api/v1/sources").json() == []


def test_pdf_upload_succeeds(client):
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("handbook.pdf", PDF_WITH_TEXT, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "handbook.pdf"
    assert body["kind"] == "pdf"
    assert body["chunk_count"] >= 1


def test_pdf_upload_uses_docling_metadata_when_available(client, app, monkeypatch):
    app.state.container.settings.pdf_parser = "docling"

    class FakeDoclingDocument:
        name = "Attention Is All You Need"
        pages = {1: object(), 2: object()}

        def export_to_markdown(self):
            return (
                "# Attention Is All You Need\n\n"
                "## Abstract\n\n"
                "Transformer attention improves sequence modeling for AI systems."
            )

    class FakeDocumentConverter:
        def convert(self, source):
            assert source.suffix == ".pdf"
            return SimpleNamespace(document=FakeDoclingDocument())

    class FakeChunker:
        def __init__(self, **_kwargs):
            pass

        def chunk(self, dl_doc):
            assert dl_doc.name == "Attention Is All You Need"
            provenance = SimpleNamespace(page_no=1)
            doc_item = SimpleNamespace(label="paragraph", prov=[provenance])
            meta = SimpleNamespace(
                headings=["Attention Is All You Need", "Abstract"],
                captions=[],
                doc_items=[doc_item],
            )
            yield SimpleNamespace(
                text="Transformer attention improves sequence modeling for AI systems.",
                meta=meta,
            )

        def contextualize(self, chunk):
            return f"Attention Is All You Need\nAbstract\n{chunk.text}"

    docling_module = ModuleType("docling")
    chunking_module = ModuleType("docling.chunking")
    chunking_module.HybridChunker = FakeChunker
    converter_module = ModuleType("docling.document_converter")
    converter_module.DocumentConverter = FakeDocumentConverter
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.chunking", chunking_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)
    monkeypatch.setattr(
        app.state.container.sources,
        "_docling_chunker",
        lambda hybrid_chunker_cls: hybrid_chunker_cls(),
    )

    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("attention.pdf", PDF_WITH_TEXT, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["chunk_count"] >= 1
    indexed = app.state.container.sources.knowledge.documents[0]
    assert indexed.metadata["parser"] == "docling"
    assert indexed.metadata["document_type"] == "ai_computer_science_paper"
    assert indexed.metadata["normalized_format"] == "markdown"
    assert indexed.metadata["title"] == "Attention Is All You Need"
    assert indexed.metadata["page_count"] == 2
    assert indexed.metadata["section_path"] == "Attention Is All You Need > Abstract"
    assert indexed.metadata["page_start"] == 1
    assert indexed.metadata["docling_labels"] == "paragraph"
    assert "Transformer attention" in indexed.metadata["original_text"]


def test_valid_pdf_without_extractable_text_is_saved_as_no_text_source(client):
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)

    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("scanned-or-blank.pdf", buffer.getvalue())},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "pdf"
    assert body["status"] == "no_text"
    assert body["chunk_count"] == 0
    assert client.get("/api/v1/sources").json()[0]["name"] == "scanned-or-blank.pdf"


def test_upload_uses_sparse_index_when_openai_embedding_key_is_missing(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        vector_store_provider="postgres",
        embedding_provider="openai",
        pdf_parser="pypdf",
        openai_api_key=None,
        openai_embedding_api_key=None,
        openai_admin_api_key=None,
        master_key_path=tmp_path / "master.key",
        cors_origins=["http://testserver"],
    )

    with TestClient(create_app(settings)) as test_client:
        response = test_client.post(
            "/api/v1/sources/upload",
            files={"file": ("handbook.pdf", PDF_WITH_TEXT, "application/pdf")},
        )

    assert response.status_code == 201
    assert response.json()["chunk_count"] >= 1



def test_upload_returns_configuration_error_when_indexing_fails(client, app, monkeypatch):
    def broken_add_documents(_documents):
        raise RuntimeError("embedding backend unavailable")

    monkeypatch.setattr(
        app.state.container.sources.knowledge,
        "add_documents",
        broken_add_documents,
    )

    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("handbook.md", "Atlas Pro support handbook and warranty policy.")},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "configuration_error"
    assert client.get("/api/v1/sources").json() == []


def test_pdf_upload_succeeds_when_dense_index_is_unavailable(client, app, monkeypatch):
    def unavailable_vector_store(*_args, **_kwargs):
        raise RuntimeError("vector index unavailable")

    knowledge = app.state.container.sources.knowledge
    monkeypatch.setattr(knowledge, "_should_use_sparse_only_index", lambda: False)
    monkeypatch.setattr(knowledge, "_build_vector_store", unavailable_vector_store)

    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("2024.emnlp-main.981.pdf", PDF_WITH_TEXT, "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["chunk_count"] >= 1
    assert knowledge.search("Hello PDF upload", top_k=1)


def test_chroma_vector_store_indexes_documents_without_external_service(tmp_path, monkeypatch):
    class FakeChroma:
        def __init__(self, collection_name, embedding_function, persist_directory):
            self.collection_name = collection_name
            self.embedding_function = embedding_function
            self.persist_directory = persist_directory
            self.documents = []
            self.deleted = False

        def add_documents(self, documents, ids):
            self.documents.extend(zip(ids, documents, strict=True))

        def similarity_search_with_score(self, _query, k):
            return [(document, 0.0) for _id, document in self.documents[:k]]

        def delete_collection(self):
            self.deleted = True

    chroma_module = ModuleType("langchain_chroma")
    chroma_module.Chroma = FakeChroma
    monkeypatch.setitem(sys.modules, "langchain_chroma", chroma_module)
    settings = Settings(
        data_dir=tmp_path / "data",
        chroma_persist_dir=tmp_path / "chroma",
        vector_store_provider="chroma",
        embedding_provider="local",
    )
    knowledge = KnowledgeIndex(settings)
    vector_store = knowledge._build_vector_store(LocalHashEmbeddings())

    vector_store.add_documents(
        [Document(page_content="graph neural networks", metadata={"knowledge_id": "paper-1"})]
    )

    assert vector_store.store.collection_name == "healthcare_pdf_papers"
    assert vector_store.store.persist_directory == str(tmp_path / "chroma")
    assert vector_store.similarity_search_with_score("neural", k=1)[0][0].page_content.startswith(
        "graph"
    )


def test_ragas_evaluation_endpoint_stores_json_result(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    upload = client.post(
        "/api/v1/sources/upload",
        files={"file": ("handbook.md", "Atlas Pro support handbook and warranty policy.")},
    )
    assert upload.status_code == 201
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/evaluations/ragas",
        json={
            "pipeline_id": pipeline["id"],
            "run_name": "smoke-ragas",
            "dataset": [
                {
                    "question": "문서에서 Atlas Pro 정책은?",
                    "ground_truth": "Atlas Pro support handbook and warranty policy.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_name"] == "smoke-ragas"
    assert body["ragas_backend"] in {"proxy", "ragas-installed-proxy-runner"}
    assert body["metrics"][0]["question"] == "문서에서 Atlas Pro 정책은?"
    assert set(body["averages"]) == {
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    }
    assert app.state.container.settings.ragas_results_dir.joinpath(f"{body['id']}.json").exists()

    listed = client.get("/api/v1/evaluations/ragas")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())


def test_table_upload_is_no_longer_supported(client):
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("support.csv", "product,tickets\nAtlas Pro,1284\nNova,410\n")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_non_rag_strategy_is_rejected(client):
    connect_provider(client)

    response = client.post(
        "/api/v1/pipelines",
        json={
            "name": "Invalid strategy assistant",
            "strategy": "sql",
            "provider": "openai",
            "model": "gpt-test",
        },
    )

    assert response.status_code == 422


def test_deployment_exposes_public_chat_without_auth(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("guide.txt", "Atlas Pro guide")},
    )
    pipeline = create_pipeline(client, "rag")
    deployed = client.post(
        "/api/v1/deployments",
        json={"pipeline_id": pipeline["id"], "slug": "atlas-preview"},
    )
    assert deployed.status_code == 201
    assert deployed.json()["environment"] == "preview"
    assert deployed.json()["status"] == "running"

    response = client.post("/api/v1/public/atlas-preview/chat", json={"message": "Atlas란?"})
    assert response.status_code == 200


def test_deployment_executes_immutable_pipeline_version(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("guide.txt", "Atlas Pro guide")},
    )
    pipeline = create_pipeline(client, "rag")
    deployed = client.post(
        "/api/v1/deployments",
        json={"pipeline_id": pipeline["id"], "slug": "immutable-preview"},
    )
    assert deployed.status_code == 201

    updated = client.patch(
        f"/api/v1/pipelines/{pipeline['id']}",
        json={"model": "changed-draft-model"},
    )
    assert updated.status_code == 200
    response = client.post("/api/v1/public/immutable-preview/chat", json={"message": "Atlas란?"})

    assert response.status_code == 200
    assert response.json()["strategy"] == "rag"
    assert response.json()["model"] == "gpt-test"


def test_deployment_can_stop_run_change_environment_and_delete(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("lifecycle.txt", "Deployment lifecycle guide")},
    )
    pipeline = create_pipeline(client, "rag")
    deployed = client.post(
        "/api/v1/deployments",
        json={
            "pipeline_id": pipeline["id"],
            "slug": "lifecycle-preview",
            "environment": "preview",
        },
    ).json()

    promoted = client.patch(
        f"/api/v1/deployments/{deployed['id']}",
        json={"environment": "production"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["environment"] == "production"
    assert promoted.json()["status"] == "running"

    stopped = client.post(f"/api/v1/deployments/{deployed['id']}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    unavailable = client.post(
        "/api/v1/public/lifecycle-preview/chat",
        json={"message": "hello"},
    )
    assert unavailable.status_code == 409

    running = client.post(f"/api/v1/deployments/{deployed['id']}/run")
    assert running.status_code == 200
    assert running.json()["status"] == "running"
    available = client.post(
        "/api/v1/public/lifecycle-preview/chat",
        json={"message": "hello"},
    )
    assert available.status_code == 200

    deleted = client.delete(f"/api/v1/deployments/{deployed['id']}")
    assert deleted.status_code == 204
    assert client.post(
        "/api/v1/public/lifecycle-preview/chat",
        json={"message": "hello"},
    ).status_code == 404


def test_pipeline_requires_connected_provider(client):
    response = client.post(
        "/api/v1/pipelines",
        json={"name": "Invalid pipeline", "provider": "openai", "model": "gpt-test"},
    )
    assert response.status_code == 404


def test_rollback_creates_deployable_immutable_head(client):
    connect_provider(client)
    pipeline = create_pipeline(client, "rag")
    client.patch(
        f"/api/v1/pipelines/{pipeline['id']}",
        json={"model": "changed-draft-model"},
    )
    saved = client.post(f"/api/v1/pipelines/{pipeline['id']}/versions")
    assert saved.status_code == 201
    assert saved.json()["version"] == 2

    rolled_back = client.post(f"/api/v1/pipelines/{pipeline['id']}/rollback/1")
    assert rolled_back.status_code == 200
    assert rolled_back.json()["strategy"] == "rag"
    assert rolled_back.json()["current_version"] == 3
    versions = client.get(f"/api/v1/pipelines/{pipeline['id']}/versions").json()
    assert versions[0]["version"] == 3
    assert versions[0]["config"]["strategy"] == "rag"


def test_delete_pipeline_removes_versions_and_deployments(client):
    connect_provider(client)
    pipeline = create_pipeline(client, "rag")
    saved = client.post(f"/api/v1/pipelines/{pipeline['id']}/versions")
    assert saved.status_code == 201
    deployed = client.post(
        "/api/v1/deployments",
        json={"pipeline_id": pipeline["id"], "slug": "delete-target"},
    )
    assert deployed.status_code == 201

    deleted = client.delete(f"/api/v1/pipelines/{pipeline['id']}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/v1/pipelines/{pipeline['id']}").status_code == 404
    assert client.get(f"/api/v1/pipelines/{pipeline['id']}/versions").status_code == 404
    public_chat = client.post(
        "/api/v1/public/delete-target/chat",
        json={"message": "hello"},
    )
    assert public_chat.status_code == 404
    assert all(item["id"] != pipeline["id"] for item in client.get("/api/v1/pipelines").json())
    assert all(
        item["slug"] != "delete-target" for item in client.get("/api/v1/deployments").json()
    )


def test_delete_pipeline_returns_404_for_unknown_pipeline(client):
    response = client.delete("/api/v1/pipelines/unknown-pipeline")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_chat_stream_emits_trace_tokens_and_done(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("stream.txt", "Streaming with LangChain")},
    )
    pipeline = create_pipeline(client, "rag")

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"pipeline_id": pipeline["id"], "message": "스트리밍 테스트"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: trace" in body
    assert "event: token" in body
    assert "event: done" in body


def test_chat_stream_emits_error_event_for_runtime_failures(client, app, monkeypatch):
    connect_provider(client)

    async def failing_model(*_args, **_kwargs):
        return FailingStreamModel()

    monkeypatch.setattr(app.state.container.orchestrator, "_model", failing_model)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("guide.txt", "RAG guide")},
    )
    pipeline = create_pipeline(client, "rag")

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"pipeline_id": pipeline["id"], "message": "hello"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: error" in body
    assert "model unavailable" in body


def test_chat_stream_falls_back_to_local_model_for_provider_quota(client, app, monkeypatch):
    connect_provider(client)

    async def quota_limited_model(*_args, **_kwargs):
        return QuotaLimitedModel()

    monkeypatch.setattr(app.state.container.orchestrator, "_model", quota_limited_model)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("guide.txt", "RAG guide")},
    )
    pipeline = create_pipeline(client, "rag")

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"pipeline_id": pipeline["id"], "message": "hello"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: token" in body
    assert "event: done" in body
    assert "event: error" not in body
    assert "local_model" in body
    assert "insufficient_quota" in body


def test_chat_falls_back_to_local_model_for_provider_quota(client, app, monkeypatch):
    connect_provider(client)

    async def quota_limited_model(*_args, **_kwargs):
        return QuotaLimitedModel()

    monkeypatch.setattr(app.state.container.orchestrator, "_model", quota_limited_model)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("guide.txt", "RAG guide")},
    )
    pipeline = create_pipeline(client, "rag")

    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "hello"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["trace"][-1]["metadata"]["fallback"] == "local_model"
    assert "insufficient_quota" in body["trace"][-1]["metadata"]["fallback_reason"]


def test_stream_chat_persists_session_and_uses_history(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("memory.txt", "Conversation memory with LangChain")},
    )
    pipeline = create_pipeline(client, "rag")

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"pipeline_id": pipeline["id"], "message": "첫 질문입니다"},
    ) as first_response:
        first_body = "".join(first_response.iter_text())

    assert first_response.status_code == 200
    sessions = client.get(f"/api/v1/chat/sessions?pipeline_id={pipeline['id']}").json()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]
    assert f'"session_id": "{session_id}"' in first_body
    messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages").json()
    assert [message["role"] for message in messages] == ["user", "assistant"]

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={
            "pipeline_id": pipeline["id"],
            "session_id": session_id,
            "message": "방금 질문을 기억하나요?",
        },
    ) as second_response:
        "".join(second_response.iter_text())

    assert second_response.status_code == 200
    second_call_messages = FakeChatModel.seen_messages[-1]
    assert any(message.content == "첫 질문입니다" for message in second_call_messages)
    assert any(message.content == "Atlas Pro가 가장 많습니다." for message in second_call_messages)
    messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages").json()
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_chat_session_title_can_be_set_and_renamed(client):
    connect_provider(client)
    pipeline = create_pipeline(client, "rag")
    created = client.post(
        "/api/v1/chat/sessions",
        json={"pipeline_id": pipeline["id"], "title": "초기 대화 이름"},
    )
    assert created.status_code == 201

    renamed = client.patch(
        f"/api/v1/chat/sessions/{created.json()['id']}",
        json={"title": "  운영 FAQ 테스트  "},
    )

    assert renamed.status_code == 200
    assert renamed.json()["title"] == "운영 FAQ 테스트"
    sessions = client.get(f"/api/v1/chat/sessions?pipeline_id={pipeline['id']}").json()
    assert sessions[0]["title"] == "운영 FAQ 테스트"


def test_status_command_reports_session_token_usage_without_model_call(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("status.txt", "Token usage guide")},
    )
    pipeline = create_pipeline(client, "rag")
    first = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "토큰 사용량을 만들 질문"},
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]
    model_calls = len(FakeChatModel.seen_messages)

    status_response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "session_id": session_id, "message": "/status"},
    )

    assert status_response.status_code == 200
    assert len(FakeChatModel.seen_messages) == model_calls
    body = status_response.json()
    assert body["strategy"] == "status"
    assert "Used total: 28 tokens" in body["answer"]
    assert "Remaining: 99,972 tokens" in body["answer"]
    assert body["provider_quota"]["openai"]["configured"] is False


def test_status_command_streams_token_usage(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    pipeline = create_pipeline(client, "rag")
    first = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "스트림 status 준비"},
    )
    session_id = first.json()["session_id"]

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"pipeline_id": pipeline["id"], "session_id": session_id, "message": "/status"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: token" in body
    assert "Session token status" in body
    assert "event: done" in body


def test_status_command_includes_provider_quota(client, app, monkeypatch):
    connect_provider(client)
    pipeline = create_pipeline(client, "rag")

    async def fake_status():
        return {
            "period": {
                "start": "2026-06-01T00:00:00Z",
                "end": "2026-06-25T00:00:00Z",
                "bucket_width": "1d",
            },
            "openai": {
                "configured": True,
                "usage": {"available": True, "total_tokens": 1234, "tokens": {}, "requests": {}},
                "cost": {"available": True, "amount": 0.42, "currency": "USD"},
                "remaining": {"available": False, "reason": "not exposed"},
            },
            "anthropic": {
                "configured": True,
                "usage": {"available": True, "total_tokens": 500, "tokens": {}, "requests": {}},
                "cost": {"available": True, "amount": 0.2, "currency": "USD"},
                "remaining": {"available": True, "remaining_usd": 99.8},
            },
        }

    monkeypatch.setattr(app.state.container.provider_quota, "status", fake_status)

    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "/status"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider_quota"]["openai"]["usage"]["total_tokens"] == 1234
    assert body["provider_quota"]["anthropic"]["remaining"]["remaining_usd"] == 99.8
    assert "OpenAI: used 1,234 tokens" in body["answer"]
    assert "Anthropic: used 500 tokens" in body["answer"]
