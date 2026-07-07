from datetime import datetime
from typing import Any

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


class RagasDatasetItem(BaseModel):
    question: str = Field(min_length=1)
    answer: str | None = None
    contexts: list[str] = Field(default_factory=list)
    ground_truth: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagasEvaluationRequest(BaseModel):
    pipeline_id: str
    dataset: list[RagasDatasetItem] = Field(default_factory=list)
    dataset_path: str | None = None
    run_name: str | None = None


class RagasMetricScore(BaseModel):
    question: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    route: str
    latency_ms: float | None = None


class RagasEvaluationResponse(BaseModel):
    id: str
    pipeline_id: str
    run_name: str
    executed_at: datetime
    result_path: str
    metrics: list[RagasMetricScore]
    averages: dict[str, float]
    config: dict[str, Any]
    ragas_backend: str
