
import pytest

from app.schemas.writing import LiteratureDraft
from app.services.rag_writer import (
    CitationValidationError,
    _validate_citations,
)


def make_draft(evidence_ids):
    return LiteratureDraft(
        title="Test draft",
        executive_summary="Test summary.",
        key_findings=[
            {
                "statement": "A reported finding.",
                "evidence_ids": evidence_ids,
            }
        ],
        limitations=[],
        evidence_gaps=[],
        conclusion="Draft conclusion.",
    )


@pytest.fixture
def lookup():
    return {
        "E1": {
            "evidence_id": "E1",
            "chunk_id": "doc123_0",
            "document_id": "doc123",
            "filename": "study.pdf",
            "page_start": 2,
            "page_end": 2,
        }
    }


def test_valid_citation_maps_to_source(lookup):
    draft = make_draft(["E1"])

    citations, warnings = _validate_citations(draft, lookup)

    assert len(citations) == 1
    assert citations[0].filename == "study.pdf"
    assert citations[0].page_start == 2


def test_unknown_citation_is_rejected(lookup):
    draft = make_draft(["E99"])

    with pytest.raises(CitationValidationError, match="unknown evidence ID"):
        _validate_citations(draft, lookup)


def test_uncited_finding_is_flagged(lookup):
    draft = make_draft([])

    citations, warnings = _validate_citations(draft, lookup)

    assert citations == []
    assert any("Uncited finding" in w for w in warnings)


def test_duplicate_citations_are_removed(lookup):
    draft = make_draft(["E1", "E1"])

    citations, warnings = _validate_citations(draft, lookup)

    assert draft.key_findings[0].evidence_ids == ["E1"]
    assert len(citations) == 1
