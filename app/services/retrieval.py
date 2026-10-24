from app.services.vector_store import search_chunks


def retrieve_evidence(
    query: str,
    project_id: str,
    top_k: int = 5,
    document_ids: list[str] | None = None,
    page_from: int | None = None,
    page_to: int | None = None,
) -> list[dict]:
    """
    Retrieve source passages for a research question.

    The returned passages are evidence candidates, not verified answers.
    """
    query = query.strip() if query else ""

    if len(query) < 3:
        raise ValueError("Query must contain at least 3 characters.")

    if not project_id:
        raise ValueError("project_id is required.")

    return search_chunks(
        query=query,
        project_id=project_id,
        top_k=top_k,
        document_ids=document_ids,
        page_from=page_from,
        page_to=page_to,
    )
