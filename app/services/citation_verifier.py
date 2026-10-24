"""Citation verification service."""
from app.services.vector_store import get_chunk_by_id


def resolve_citations(evidence_ids, citation_lookup):
    """
    Resolve caller-provided evidence IDs to exact indexed passages.

    citation_lookup maps IDs such as E1 to the citation metadata
    returned by Day 6 or Day 7.
    """
    resolved = []

    for evidence_id in dict.fromkeys(evidence_ids):
        citation = citation_lookup.get(evidence_id)

        if not citation:
            raise ValueError(
                f"Unknown evidence ID: {evidence_id}"
            )

        chunk_id = citation.get("chunk_id")
        if not chunk_id:
            raise ValueError(
                f"Missing chunk ID for evidence: {evidence_id}"
            )

        chunk = get_chunk_by_id(chunk_id)

        if not chunk or not chunk.get("text"):
            raise ValueError(
                f"Source passage is unavailable for {evidence_id}"
            )

        metadata = chunk.get("metadata") or {}

        # Ensure the source still belongs to the expected project
        # and document before using its text.
        if str(metadata.get("project_id")) != str(
            citation.get("project_id", metadata.get("project_id"))
        ):
            raise ValueError(
                f"Project metadata mismatch for {evidence_id}"
            )

        if str(metadata.get("document_id")) != str(
            citation.get("document_id")
        ):
            raise ValueError(
                f"Document metadata mismatch for {evidence_id}"
            )

        resolved.append({
            "evidence_id": evidence_id,
            "chunk_id": chunk_id,
            "document_id": str(metadata.get("document_id", "")),
            "filename": metadata.get("filename", "Unknown"),
            "page_start": metadata.get("page_start"),
            "page_end": metadata.get("page_end"),
            "text": chunk["text"],
        })

    return resolved