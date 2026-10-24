
def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be at least 1.")

    if not relevant_ids:
        return 0.0

    retrieved = set(retrieved_ids[:k])
    return len(retrieved & relevant_ids) / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be at least 1.")

    top_k = retrieved_ids[:k]

    if not top_k:
        return 0.0

    relevant_count = sum(
        1 for item in top_k if item in relevant_ids
    )
    return relevant_count / k


def reciprocal_rank(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    for rank, item in enumerate(retrieved_ids, start=1):
        if item in relevant_ids:
            return 1.0 / rank

    return 0.0


def evaluate_retrieval(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> dict:
    return {
        f"recall@{k}": round(
            recall_at_k(retrieved_ids, relevant_ids, k), 4
        ),
        f"precision@{k}": round(
            precision_at_k(retrieved_ids, relevant_ids, k), 4
        ),
        "mrr": round(
            reciprocal_rank(retrieved_ids, relevant_ids), 4
        ),
    }
