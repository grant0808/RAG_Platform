from fastapi.testclient import TestClient

from foundry.cli import bootstrap_local, initialize_database
from foundry.core.config import Settings
from foundry.main import create_app


def local_settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'local.db'}",
        master_key_path=tmp_path / "master.key",
        fake_llm_enabled=True,
    )


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
        assert len(client.get("/api/v1/sources").json()) == 2
        assert len(client.get("/api/v1/pipelines").json()) == 3

        response = client.post(
            "/api/v1/public/local-rag-preview/chat",
            json={"message": "Foundry의 응답 속도 목표는?"},
        )

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-local-demo"
    assert "로컬 테스트 모델" in response.json()["answer"]
