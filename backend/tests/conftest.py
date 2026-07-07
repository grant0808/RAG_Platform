from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from foundry.core.config import Settings
from foundry.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        vector_store_provider="memory",
        embedding_provider="local",
        pdf_parser="pypdf",
        openai_api_key=None,
        openai_embedding_api_key=None,
        openai_admin_api_key=None,
        web_fallback_provider="none",
        master_key_path=tmp_path / "master.key",
        cors_origins=["http://testserver"],
    )
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
