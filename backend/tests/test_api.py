from langchain_core.messages import AIMessage, AIMessageChunk


class FakeChatModel:
    async def ainvoke(self, messages):
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

    response = client.post("/api/v1/public/atlas-preview/chat", json={"message": "Atlas란?"})
    assert response.status_code == 200


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
