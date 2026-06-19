from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    pipeline_id: str
    test_queries: list[str] = Field(default_factory=list)


class EvaluationMetric(BaseModel):
    query: str
    strategy: str
    latency_seconds: float
    estimated_cost: float
    accuracy_score: float


class EvaluationResultResponse(BaseModel):
    pipeline_id: str
    executed_at: datetime
    average_latency_seconds: float
    total_estimated_cost: float
    average_accuracy_score: float
    metrics: list[EvaluationMetric]
