from __future__ import annotations

import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.config import Settings
from foundry.core.errors import ValidationError
from foundry.models import Pipeline
from foundry.schemas.evaluation import (
    RagasDatasetItem,
    RagasEvaluationResponse,
    RagasMetricScore,
)
from foundry.services.orchestrator import Orchestrator


class RagasEvaluationService:
    def __init__(self, settings: Settings, orchestrator: Orchestrator) -> None:
        self.settings = settings
        self.orchestrator = orchestrator

    async def run(
        self,
        session: AsyncSession,
        pipeline: Pipeline,
        *,
        dataset: list[RagasDatasetItem],
        dataset_path: str | None,
        run_name: str | None,
    ) -> RagasEvaluationResponse:
        items = dataset or self._load_dataset(dataset_path)
        if not items:
            raise ValueError("RAGAS evaluation requires at least one dataset item")

        metric_rows: list[RagasMetricScore] = []
        raw_rows: list[dict] = []
        prepared_rows: list[dict] = []
        for item in items:
            result = await self.orchestrator.invoke(
                session,
                pipeline,
                item.question,
                pipeline.strategy,
            )
            contexts = self._normalize_contexts(result.get("contexts") or item.contexts)
            answer = str(result.get("answer") or item.answer or "")
            prepared_rows.append(
                {
                    "question": item.question,
                    "answer": answer,
                    "contexts": contexts,
                    "ground_truth": item.ground_truth,
                }
            )
            scores = self._proxy_scores(item.question, answer, contexts, item.ground_truth)
            metric_rows.append(
                RagasMetricScore(
                    question=item.question,
                    route=str(result.get("route", "rag")),
                    latency_ms=result.get("latency_ms"),
                    **scores,
                )
            )
            raw_rows.append(
                {
                    "question": item.question,
                    "answer": answer,
                    "contexts": contexts,
                    "ground_truth": item.ground_truth,
                    "route": result.get("route"),
                    "latency_ms": result.get("latency_ms"),
                    "sources": result.get("sources", []),
                    "metadata": item.metadata,
                    "scores": scores,
                }
            )

        run_id = str(uuid4())
        executed_at = datetime.now(UTC)
        ragas_scores = self._try_ragas(prepared_rows)
        ragas_backend = "ragas" if ragas_scores else self._ragas_backend()
        if ragas_scores:
            metric_rows = [
                RagasMetricScore(
                    question=row["question"],
                    route=raw_row["route"] or "rag",
                    latency_ms=raw_row.get("latency_ms"),
                    **scores,
                )
                for row, raw_row, scores in zip(prepared_rows, raw_rows, ragas_scores, strict=True)
            ]
        averages = self._averages(metric_rows)
        result_path = self._write_result(
            run_id,
            {
                "id": run_id,
                "pipeline_id": pipeline.id,
                "run_name": run_name or "ragas-evaluation",
                "executed_at": executed_at.isoformat(),
                "items": raw_rows,
                "averages": averages,
                "config": self._config(pipeline),
                "ragas_backend": ragas_backend,
            },
        )
        return RagasEvaluationResponse(
            id=run_id,
            pipeline_id=pipeline.id,
            run_name=run_name or "ragas-evaluation",
            executed_at=executed_at,
            result_path=str(result_path),
            metrics=metric_rows,
            averages=averages,
            config=self._config(pipeline),
            ragas_backend=ragas_backend,
        )

    def list_results(self) -> list[dict]:
        results = []
        for path in sorted(self.settings.ragas_results_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                results.append(
                    {
                        "id": payload.get("id", path.stem),
                        "run_name": payload.get("run_name"),
                        "pipeline_id": payload.get("pipeline_id"),
                        "executed_at": payload.get("executed_at"),
                        "averages": payload.get("averages", {}),
                        "result_path": str(path),
                    }
                )
            except json.JSONDecodeError:
                continue
        return results

    def _load_dataset(self, dataset_path: str | None) -> list[RagasDatasetItem]:
        if not dataset_path:
            return []
        path = Path(dataset_path).expanduser()
        if not path.exists():
            raise ValidationError(f"RAGAS dataset not found: {dataset_path}")
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data.get("items", data) if isinstance(data, dict) else data
            return [RagasDatasetItem.model_validate(row) for row in rows]
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8", newline="") as file:
                return [self._item_from_csv_row(row) for row in csv.DictReader(file)]
        raise ValidationError("RAGAS dataset_path must point to a .json or .csv file")

    def _try_ragas(self, rows: list[dict]) -> list[dict[str, float]] | None:
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )
        except ImportError:
            return None
        try:
            result = evaluate(
                Dataset.from_list(rows),
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            )
        except Exception:
            return None
        frame = result.to_pandas()
        return [
            {
                "faithfulness": float(record.get("faithfulness") or 0.0),
                "answer_relevancy": float(record.get("answer_relevancy") or 0.0),
                "context_precision": float(record.get("context_precision") or 0.0),
                "context_recall": float(record.get("context_recall") or 0.0),
            }
            for record in frame.to_dict(orient="records")
        ]

    @staticmethod
    def _item_from_csv_row(row: dict[str, str]) -> RagasDatasetItem:
        contexts_raw = row.get("contexts") or ""
        contexts = _parse_contexts(contexts_raw)
        return RagasDatasetItem(
            question=row.get("question", ""),
            answer=row.get("answer") or None,
            contexts=contexts,
            ground_truth=row.get("ground_truth", ""),
        )

    def _write_result(self, run_id: str, payload: dict) -> Path:
        self.settings.ragas_results_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.ragas_results_dir / f"{run_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _proxy_scores(
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str,
    ) -> dict[str, float]:
        question_terms = _terms(question)
        answer_terms = _terms(answer)
        truth_terms = _terms(ground_truth)
        context_terms = _terms(" ".join(contexts))
        return {
            "faithfulness": _overlap(answer_terms, context_terms),
            "answer_relevancy": _overlap(question_terms, answer_terms),
            "context_precision": _overlap(question_terms, context_terms),
            "context_recall": _overlap(truth_terms, context_terms),
        }

    @staticmethod
    def _normalize_contexts(contexts: object) -> list[str]:
        if not isinstance(contexts, list):
            return []
        normalized: list[str] = []
        for context in contexts:
            if isinstance(context, str):
                normalized.append(context)
            elif isinstance(context, dict):
                value = context.get("content")
                normalized.append(str(value if value is not None else context))
            else:
                normalized.append(str(context))
        return normalized

    @staticmethod
    def _averages(rows: list[RagasMetricScore]) -> dict[str, float]:
        fields = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        return {
            field: round(sum(getattr(row, field) for row in rows) / len(rows), 4)
            for field in fields
        }

    def _config(self, pipeline: Pipeline) -> dict:
        return {
            "embedding_model": self.settings.huggingface_embedding_model,
            "vector_store": self.settings.vector_store_provider,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "top_k": pipeline.top_k,
            "similarity_threshold": pipeline.similarity_threshold,
            "provider": pipeline.provider,
            "model": pipeline.model,
        }

    @staticmethod
    def _ragas_backend() -> str:
        try:
            import ragas  # noqa: F401
        except ImportError:
            return "proxy"
        return "ragas-installed-proxy-runner"


def _terms(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_\uac00-\ud7a3]+", text)}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left:
        return 0.0
    return round(len(left & right) / len(left), 4)


def _parse_contexts(value: str) -> list[str]:
    if not value:
        return []
    if value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in value.split("||") if item.strip()]
