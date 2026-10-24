"""Tests for evidence retrieval, to be added with the retriever implementation."""

import pytest

from app.services.retrieval_evaluation import (
    evaluate_retrieval,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k():
    retrieved = ["A", "B", "C"]
    relevant = {"B", "C", "D"}

    assert recall_at_k(retrieved, relevant, 3) == pytest.approx(2 / 3)


def test_precision_at_k():
    retrieved = ["A", "B", "C", "D"]
    relevant = {"B", "D"}

    assert precision_at_k(retrieved, relevant, 4) == pytest.approx(0.5)


def test_reciprocal_rank():
    retrieved = ["A", "B", "C"]
    relevant = {"C"}

    assert reciprocal_rank(retrieved, relevant) == pytest.approx(1 / 3)


def test_no_relevant_result():
    assert reciprocal_rank(["A", "B"], {"Z"}) == 0.0


def test_empty_relevance_set():
    assert recall_at_k(["A", "B"], set(), 2) == 0.0


def test_invalid_k():
    with pytest.raises(ValueError):
        recall_at_k(["A"], {"A"}, 0)


def test_combined_metrics():
    result = evaluate_retrieval(
        retrieved_ids=["A", "B", "C"],
        relevant_ids={"B", "C"},
        k=3,
    )

    assert result == {
        "recall@3": 1.0,
        "precision@3": round(2 / 3, 4),
        "mrr": 0.5,
    }
