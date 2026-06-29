from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk

from foundry.core.config import Settings
from foundry.main import create_app

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
        system_text = str(messages[0].content)
        if "Generate exactly one DuckDB SELECT query" in system_text:
            return AIMessage(
                content='SELECT product, tickets FROM "source_table" ORDER BY tickets DESC'
            )
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


def test_upload_uses_sparse_index_when_openai_embedding_key_is_missing(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        vector_store_provider="postgres",
        embedding_provider="openai",
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


def test_tag_executes_only_validated_select(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    upload = client.post(
        "/api/v1/sources/upload",
        files={"file": ("support.csv", "product,tickets\nAtlas Pro,1284\nNova,410\n")},
    )
    assert upload.status_code == 201
    table_name = upload.json()["table_name"]

    original_ainvoke = FakeChatModel.ainvoke

    async def tag_aware_ainvoke(self, messages):
        if "Generate exactly one DuckDB SELECT query" in str(messages[0].content):
            return AIMessage(
                content=f'SELECT product, tickets FROM "{table_name}" ORDER BY tickets DESC'
            )
        return await original_ainvoke(self, messages)

    monkeypatch.setattr(FakeChatModel, "ainvoke", tag_aware_ainvoke)
    pipeline = create_pipeline(client, "tag")
    response = client.post(
        "/api/v1/chat",
        json={"pipeline_id": pipeline["id"], "message": "문의가 가장 많은 제품은?"},
    )

    assert response.status_code == 200
    assert any(event["step"] == "safe_sql_tool" for event in response.json()["trace"])


def test_cag_returns_cached_second_response(client, app, monkeypatch):
    connect_provider(client)
    install_fake_model(app, monkeypatch)
    client.post(
        "/api/v1/sources/upload",
        files={"file": ("metrics.txt", "The p95 target is three seconds.")},
    )
    pipeline = create_pipeline(client, "cag")
    payload = {"pipeline_id": pipeline["id"], "message": "응답 목표는?"}

    first = client.post("/api/v1/chat", json=payload)
    second = client.post("/api/v1/chat", json=payload)

    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert second.status_code == 200
    assert second.json()["cached"] is True


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
        json={"strategy": "cag", "model": "changed-draft-model"},
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
        json={"strategy": "cag"},
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
