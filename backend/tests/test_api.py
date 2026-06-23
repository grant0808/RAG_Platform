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
