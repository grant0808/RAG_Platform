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
