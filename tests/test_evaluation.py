
import pytest

from app.services.evaluation import (
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    citation_validity,
    claim_label_accuracy,
)


def test_recall_at_k():
    assert recall_at_k(
        ["a", "b", "x"], {"a", "b", "c"}, 3
    ) == pytest.approx(2 / 3)


def test_precision_at_k():
    assert precision_at_k(
        ["a", "x", "b"], {"a", "b"}, 3
    ) == pytest.approx(2 / 3)


def test_reciprocal_rank():
    assert reciprocal_rank(
        ["x", "b", "a"], {"a", "b"}
    ) == pytest.approx(0.5)


def test_no_relevant_result():
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_citation_validity():
    result = citation_validity(
        ["E1", "E2", "E1"],
        {"E1", "E2"},
    )
    assert result["all_valid"] is True
    assert result["total_citations"] == 3
    assert result["valid_citations"] == 3


def test_unknown_citation_is_invalid():
    result = citation_validity(["E1", "E9"], {"E1"})
    assert result["all_valid"] is False
    assert result["invalid_ids"] == ["E9"]


def test_claim_label_accuracy():
    assert claim_label_accuracy(
        ["supported", "insufficient_evidence"],
        ["supported", "insufficient_evidence"],
    ) == 1.0


def test_claim_label_length_mismatch():
    with pytest.raises(ValueError):
        claim_label_accuracy(["supported"], [])
