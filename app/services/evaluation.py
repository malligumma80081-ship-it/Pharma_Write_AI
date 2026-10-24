"""Evaluation helpers for generated drafts."""

from typing import Any


def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> float:
    """Fraction of known relevant chunks found in the top k results."""
    if not relevant_ids:
        return 0.0

    found = set(retrieved_ids[:k]) & relevant_ids
    return len(found) / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> float:
    """Fraction of the top k retrieved chunks that are relevant."""
    if k <= 0:
        raise ValueError("k must be greater than zero.")

    top_k = retrieved_ids[:k]

    if not top_k:
        return 0.0

    relevant_count = sum(
        1 for chunk_id in top_k if chunk_id in relevant_ids
    )
    return relevant_count / len(top_k)


def reciprocal_rank(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """Reciprocal rank of the first relevant result."""
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def citation_validity(
    cited_ids: list[str],
    allowed_ids: set[str],
) -> dict[str, Any]:
    """Check citation references against the supplied evidence set."""
    invalid_ids = sorted(set(cited_ids) - allowed_ids)

    return {
        "total_citations": len(cited_ids),
        "valid_citations": sum(
            1 for evidence_id in cited_ids
            if evidence_id in allowed_ids
        ),
        "invalid_ids": invalid_ids,
        "all_valid": len(invalid_ids) == 0,
    }


def claim_label_accuracy(
    expected_labels: list[str],
    predicted_labels: list[str],
) -> float:
    """Compare predicted labels with manually reviewed reference labels."""
    if len(expected_labels) != len(predicted_labels):
        raise ValueError("Expected and predicted labels must have equal length.")

    if not expected_labels:
        return 0.0

    correct = sum(
        expected == predicted
        for expected, predicted in zip(
            expected_labels, predicted_labels
        )
    )
    return correct / len(expected_labels)
