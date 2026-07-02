from fastapi.testclient import TestClient

from foundry.cli import bootstrap_local, initialize_database
from foundry.core.config import Settings
from foundry.main import create_app
from foundry.services.knowledge import KnowledgeIndex


def local_settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'local.db'}",
        vector_store_provider="memory",
        embedding_provider="local",
        pdf_parser="pypdf",
        openai_api_key=None,
        openai_embedding_api_key=None,
        openai_admin_api_key=None,
        master_key_path=tmp_path / "master.key",
        fake_llm_enabled=True,
    )


def test_local_bootstrap_settings_avoid_external_embedding_and_vector_services(tmp_path):
    settings = local_settings(tmp_path)

    assert settings.embedding_provider == "local"
    assert settings.vector_store_provider == "memory"


def test_empty_embedding_key_falls_back_to_admin_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(
        embedding_provider="openai",
        openai_embedding_api_key="",
        openai_admin_api_key="admin-test-key",
    )

    assert KnowledgeIndex(settings)._configured_openai_api_key() == "admin-test-key"


async def test_initialize_database_creates_sqlite_schema(tmp_path):
    settings = local_settings(tmp_path)

    await initialize_database(settings)

    assert (tmp_path / "local.db").is_file()


async def test_bootstrap_is_idempotent_and_supports_local_chat(tmp_path):
    settings = local_settings(tmp_path)

    first = await bootstrap_local(settings)
    second = await bootstrap_local(settings)

    assert first["deployment_slug"] == "local-rag-preview"
    assert second == first

    with TestClient(create_app(settings)) as client:
        assert len(client.get("/api/v1/providers").json()) == 1
        assert len(client.get("/api/v1/sources").json()) == 1
        assert len(client.get("/api/v1/pipelines").json()) == 1

        response = client.post(
            "/api/v1/public/local-rag-preview/chat",
            json={"message": "What is Foundry's answer latency goal?"},
        )

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-local-demo"
    assert "로컬 deterministic 테스트 모델" in response.json()["answer"]
