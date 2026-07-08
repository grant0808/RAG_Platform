import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas.evaluation import (
    EvaluationMetric,
    EvaluationResultResponse,
    EvaluationRunRequest,
    RagasEvaluationRequest,
    RagasEvaluationResponse,
)

router = APIRouter(prefix="/evaluations", tags=["evaluation"])
rag_router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/run", response_model=EvaluationResultResponse)
async def run_evaluation(
    payload: EvaluationRunRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> EvaluationResultResponse:
    try:
        pipeline = await container.pipelines.get(session, payload.pipeline_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Pipeline not found") from None

    queries = payload.test_queries
    if not queries:
        queries = [
            "지난 분기 문의가 가장 많았던 제품은?",
            "고객 데이터 보안 정책은 어떻게 되나요?",
            "파이프라인의 응답 속도 목표는?",
        ]

    metrics = []
    total_latency = 0.0
    total_cost = 0.0
    total_accuracy = 0.0

    for query in queries:
        start_time = time.perf_counter()
        try:
            result = await container.orchestrator.invoke(
                session, pipeline, query, pipeline.strategy
            )
            latency = time.perf_counter() - start_time
            # Without labeled expected answers, report a deterministic grounding proxy:
            # whether the execution produced at least one source citation. This avoids
            # presenting fabricated random values as evaluation accuracy.
            accuracy = 1.0 if result.get("citations") else 0.0
            cost = 0.015 if pipeline.provider == "openai" else 0.025
            if result.get("cached"):
                latency = 0.05
                cost = 0.001

            metrics.append(
                EvaluationMetric(
                    query=query,
                    strategy=result.get("strategy", pipeline.strategy),
                    latency_seconds=round(latency, 3),
                    estimated_cost=cost,
                    accuracy_score=accuracy,
                )
            )
            total_latency += latency
            total_cost += cost
            total_accuracy += accuracy
        except Exception:
            metrics.append(
                EvaluationMetric(
                    query=query,
                    strategy=pipeline.strategy,
                    latency_seconds=0.0,
                    estimated_cost=0.0,
                    accuracy_score=0.0,
                )
            )

    n = len(queries)
    return EvaluationResultResponse(
        pipeline_id=payload.pipeline_id,
        executed_at=datetime.now(UTC),
        average_latency_seconds=round(total_latency / n, 3) if n > 0 else 0.0,
        total_estimated_cost=round(total_cost, 4),
        average_accuracy_score=round(total_accuracy / n, 2) if n > 0 else 0.0,
        metrics=metrics,
    )


@router.post("/ragas", response_model=RagasEvaluationResponse)
async def run_ragas_evaluation(
    payload: RagasEvaluationRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> RagasEvaluationResponse:
    try:
        pipeline = await container.pipelines.get(session, payload.pipeline_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Pipeline not found") from None
    try:
        return await container.ragas_evaluation.run(
            session,
            pipeline,
            dataset=payload.dataset,
            dataset_path=payload.dataset_path,
            run_name=payload.run_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ragas")
async def list_ragas_evaluations(
    container: Container = Depends(get_container),
) -> list[dict]:
    return container.ragas_evaluation.list_results()


@rag_router.post("/evaluate", response_model=RagasEvaluationResponse)
async def run_rag_evaluation_alias(
    payload: RagasEvaluationRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> RagasEvaluationResponse:
    return await run_ragas_evaluation(payload, session, container)


@rag_router.get("/evaluations")
async def list_rag_evaluations_alias(
    container: Container = Depends(get_container),
) -> list[dict]:
    return container.ragas_evaluation.list_results()
