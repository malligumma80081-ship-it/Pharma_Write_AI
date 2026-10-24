
import json
import os
from pathlib import Path
from typing import Any

from app.services.evaluation import (
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
)
from app.services.vector_store import search_chunks


BASE_DIR = Path(__file__).resolve().parents[1]
CASES_PATH = BASE_DIR / "evals" / "retrieval_cases.json"
REPORTS_DIR = BASE_DIR / "reports"


def get_chunk_id(item):
    """Support common dictionary and object result formats."""
    if isinstance(item, dict):
        return item.get("chunk_id") or item.get("id")

    return getattr(item, "chunk_id", None) or getattr(item, "id", None)


def _normalize_case(case: Any, index: int) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise ValueError(f"Evaluation case {index} must be a JSON object.")

    case_id = case.get("case_id", f"case-{index}")
    query = case.get("query") or case.get("question")
    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            f"Evaluation case {case_id!r} must contain a non-empty "
            "'query' or 'question' field."
        )

    relevant_ids = case.get("relevant_chunk_ids")
    if (
        not isinstance(relevant_ids, list)
        or not relevant_ids
        or any(
            not isinstance(chunk_id, str) or not chunk_id.strip()
            for chunk_id in relevant_ids
        )
    ):
        raise ValueError(
            f"Evaluation case {case_id!r} must contain a non-empty list "
            "of relevant_chunk_ids."
        )

    placeholders = [
        chunk_id
        for chunk_id in relevant_ids
        if any(
            marker in chunk_id.casefold()
            for marker in ("replace", "placeholder", "your-", "real-chunk")
        )
    ]

    try:
        k = int(case.get("k", 5))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Evaluation case {case_id!r} has an invalid k; use an integer "
            "from 1 to 20."
        ) from exc
    if not 1 <= k <= 20:
        raise ValueError(
            f"Evaluation case {case_id!r} has k={k}; use a value from 1 to 20."
        )

    return {
        "case_id": str(case_id),
        "query": query.strip(),
        "relevant_chunk_ids": relevant_ids,
        "k": k,
        "placeholders": placeholders,
    }


def _get_project_id() -> str:
    value = os.environ.get("EVAL_PROJECT_ID", "").strip()
    if not value:
        raise RuntimeError(
            "Set EVAL_PROJECT_ID to the numeric ID of a project containing "
            "indexed test PDFs."
        )
    try:
        project_id = int(value)
    except ValueError as exc:
        raise RuntimeError(
            "EVAL_PROJECT_ID must be a numeric project ID, not a UUID or "
            "placeholder. Use the integer ID returned when creating the "
            "project."
        ) from exc
    if project_id < 1:
        raise RuntimeError("EVAL_PROJECT_ID must be a positive integer.")
    return str(project_id)


def main():
    project_id = _get_project_id()

    with CASES_PATH.open(encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            f"{CASES_PATH} must contain a non-empty JSON array of cases."
        )

    normalized_cases = [
        _normalize_case(case, index)
        for index, case in enumerate(cases, start=1)
    ]

    results = []
    skipped_cases = []

    for case in normalized_cases:
        if case["placeholders"]:
            skipped_cases.append(
                {
                    "case_id": case["case_id"],
                    "question": case["query"],
                    "reason": "Replace placeholder relevant_chunk_ids with "
                    "manually verified chunk IDs before scoring this case.",
                    "placeholder_chunk_ids": case["placeholders"],
                }
            )
            continue

        k = case["k"]
        relevant_ids = set(case["relevant_chunk_ids"])
        retrieved = search_chunks(
            query=case["query"],
            project_id=project_id,
            top_k=k,
        )

        retrieved_ids = [
            chunk_id
            for item in retrieved
            if (chunk_id := get_chunk_id(item)) is not None
        ]

        results.append({
            "case_id": case["case_id"],
            "question": case["query"],
            "k": k,
            "recall": recall_at_k(retrieved_ids, relevant_ids, k),
            "precision": precision_at_k(retrieved_ids, relevant_ids, k),
            "reciprocal_rank": reciprocal_rank(
                retrieved_ids, relevant_ids
            ),
            "retrieved_count": len(retrieved_ids),
        })

    count = len(results)
    report = {
        "evaluation_type": "retrieval",
        "case_count": count,
        "skipped_case_count": len(skipped_cases),
        "mean_recall": (
            sum(item["recall"] for item in results) / count
            if count else None
        ),
        "mean_precision": (
            sum(item["precision"] for item in results) / count
            if count else None
        ),
        "mean_reciprocal_rank": (
            sum(item["reciprocal_rank"] for item in results) / count
            if count else None
        ),
        "cases": results,
        "skipped_cases": skipped_cases,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / "retrieval_evaluation.json"
    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    if skipped_cases:
        print(
            f"\nSkipped {len(skipped_cases)} case(s): replace their "
            "placeholder relevant_chunk_ids with manually verified chunk IDs."
        )
    if not results:
        print(
            "No cases were scored; metrics are null until at least one case "
            "has real relevant_chunk_ids."
        )
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
