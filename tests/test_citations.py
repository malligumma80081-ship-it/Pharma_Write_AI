"""Tests for citation verification, to be added with its implementation."""
import pytest

from app.services import citation_verifier


def test_unknown_evidence_id_is_rejected():
    with pytest.raises(ValueError, match="Unknown evidence ID"):
        citation_verifier.resolve_citations(
            ["E99"],
            {},
        )


def test_missing_chunk_is_rejected(monkeypatch):
    monkeypatch.setattr(
        citation_verifier,
        "get_chunk_by_id",
        lambda chunk_id: None,
    )

    lookup = {
        "E1": {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "filename": "study.pdf",
            "page_start": 1,
            "page_end": 1,
            "project_id": "7",
        }
    }

    with pytest.raises(ValueError, match="unavailable"):
        citation_verifier.resolve_citations(["E1"], lookup)