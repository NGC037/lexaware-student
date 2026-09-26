"""Deterministic retrieval-evaluation contracts and metric helpers."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    case_id: str
    query: str
    jurisdiction: str | None
    relevant_references: tuple[str, ...]
    excluded_references: tuple[str, ...] = ()
    expected_state: Literal["results", "empty", "clarify"] = "results"


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationMetrics:
    recall_at_k: float | None
    precision_at_k: float
    relevant_source_retrieved: bool
    stale_sources_rejected: bool
    wrong_jurisdiction_rejected: bool
    empty_result_correct: bool


RETRIEVAL_EVALUATION_CASES: tuple[RetrievalEvaluationCase, ...] = (
    RetrievalEvaluationCase(
        "ordinary", "What steps after a rent deposit issue?", "IN-KA", ("tenant-deposit",)
    ),
    RetrievalEvaluationCase(
        "exact-term", "ragging complaint procedure", "IN-KA", ("anti-ragging",)
    ),
    RetrievalEvaluationCase("body-only", "When can wages be withheld?", "IN-KA", ("wage-payment",)),
    RetrievalEvaluationCase(
        "paraphrase", "My landlord kept all money after I left", "IN-KA", ("tenant-deposit",)
    ),
    RetrievalEvaluationCase(
        "ambiguous", "Can they do this?", "IN-KA", (), expected_state="clarify"
    ),
    RetrievalEvaluationCase(
        "wrong-jurisdiction", "tenant deposit return", "IN-TN", (), ("tenant-deposit-ka",), "empty"
    ),
    RetrievalEvaluationCase(
        "stale", "tenant deposit old rule", "IN-KA", (), ("tenant-deposit-expired",), "empty"
    ),
    RetrievalEvaluationCase(
        "expired", "expired tenant guidance", "IN-KA", (), ("tenant-expired",), "empty"
    ),
    RetrievalEvaluationCase(
        "unpublished", "draft complaint procedure", "IN-KA", (), ("draft-guide",), "empty"
    ),
    RetrievalEvaluationCase(
        "competing", "college complaint process", "IN-KA", ("campus-complaint", "anti-ragging")
    ),
    RetrievalEvaluationCase(
        "no-relevant", "space exploration grant", "IN-KA", (), expected_state="empty"
    ),
    RetrievalEvaluationCase(
        "multiple-relevant",
        "tenant rent deposit notice",
        "IN-KA",
        ("tenant-deposit", "tenant-notice"),
    ),
)


def evaluate_retrieval_case(
    case: RetrievalEvaluationCase,
    retrieved: list[str],
    *,
    stale_retrieved: set[str] | None = None,
    wrong_jurisdiction_retrieved: set[str] | None = None,
    k: int = 5,
) -> RetrievalEvaluationMetrics:
    if k < 1:
        raise ValueError("k must be positive.")
    selected = retrieved[:k]
    relevant = set(case.relevant_references)
    hits = len(set(selected) & relevant)
    expected_empty = case.expected_state == "empty" or not relevant
    return RetrievalEvaluationMetrics(
        recall_at_k=hits / len(relevant) if relevant else None,
        precision_at_k=hits / len(selected) if selected else (1.0 if expected_empty else 0.0),
        relevant_source_retrieved=bool(hits),
        stale_sources_rejected=not (set(stale_retrieved or ()) & set(selected)),
        wrong_jurisdiction_rejected=not (set(wrong_jurisdiction_retrieved or ()) & set(selected)),
        empty_result_correct=(not selected) if expected_empty else bool(selected),
    )
