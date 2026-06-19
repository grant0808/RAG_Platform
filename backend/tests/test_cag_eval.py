def test_cag_cache_lifecycle(client):
    # 1. 캐시 조회 (초기 상태엔 없을 것)
    response = client.get("/api/v1/cag/cache")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # 2. 캐시 수동 생성
    create_payload = {
        "key": "test_key",
        "answer": "This is a cached test answer.",
        "ttl_seconds": 100,
    }
    response = client.post("/api/v1/cag/cache", json=create_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "test_key"
    assert body["answer"] == "This is a cached test answer."

    # 3. 다시 캐시 조회 (생성한 캐시가 들어가 있어야 함)
    response = client.get("/api/v1/cag/cache")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert any(item["key"] == "test_key" for item in items)

    # 4. 캐시 삭제
    response = client.delete("/api/v1/cag/cache/test_key")
    assert response.status_code == 204

    # 5. 다시 조회하여 삭제 확인
    response = client.get("/api/v1/cag/cache")
    assert response.status_code == 200
    items = response.json()
    assert not any(item["key"] == "test_key" for item in items)


def test_pipeline_evaluation(client):
    # 1. 테스트 실행 전 공급자 연결
    client.put(
        "/api/v1/providers/openai",
        json={"api_key": "sk-test-super-secret", "validate_connection": False},
    )
    # 2. 파이프라인 생성
    pipeline_res = client.post(
        "/api/v1/pipelines",
        json={
            "name": "Eval pipeline",
            "strategy": "rag",
            "provider": "openai",
            "model": "gpt-test",
            "top_k": 3,
            "similarity_threshold": 0,
        },
    )
    assert pipeline_res.status_code == 201
    pipeline_id = pipeline_res.json()["id"]

    # 3. 평가 실행
    eval_res = client.post(
        "/api/v1/evaluations/run",
        json={
            "pipeline_id": pipeline_id,
            "test_queries": ["보안 정책은?", "지연시간 목표는?"],
        },
    )
    assert eval_res.status_code == 200
    body = eval_res.json()
    assert body["pipeline_id"] == pipeline_id
    assert "average_latency_seconds" in body
    assert "total_estimated_cost" in body
    assert "average_accuracy_score" in body
    assert len(body["metrics"]) == 2
