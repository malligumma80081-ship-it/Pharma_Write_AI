import pytest
from typing import Literal

from app.schemas.evidence import (
    EvidenceField,
    StudyEvidenceExtraction,
)
from app.services.evidence_extractor import (
    EvidenceCitationError,
    extract_study_evidence,
    _validate_extraction,
)


def make_field(
    value="Example",
    ids=None,
    status: Literal["reported", "not_reported", "conflicting", "uncertain"] = "reported",
):
    return EvidenceField(
        value=value,
        evidence_ids=ids or [],
        status=status,
    )


def make_extraction():
    return StudyEvidenceExtraction(
        study_design=make_field("Randomized controlled trial", ["E1"]),
        study_population=make_field("Adults", ["E1"]),
        sample_size=make_field("Not reported", [], "not_reported"),
        intervention=make_field("Treatment A", ["E2"]),
        comparator=make_field("Placebo", ["E2"]),
        endpoints=make_field("Primary endpoint", ["E3"]),
        outcomes=make_field("Outcome described in source", ["E3"]),
        adverse_events=make_field(
            "Not reported in retrieved evidence",
            [],
            "not_reported",
        ),
        study_limitations=make_field("Not reported", [], "not_reported"),
    )


def test_valid_evidence_ids_are_accepted():
    extraction = make_extraction()
    lookup = {"E1": {}, "E2": {}, "E3": {}}

    warnings = _validate_extraction(extraction, lookup)

    assert isinstance(warnings, list)


def test_unknown_evidence_id_is_rejected():
    extraction = make_extraction()
    extraction.study_design.evidence_ids = ["E99"]

    with pytest.raises(EvidenceCitationError):
        _validate_extraction(
            extraction,
            {"E1": {}, "E2": {}, "E3": {}},
        )


def test_reported_field_without_citation_warns():
    extraction = make_extraction()
    extraction.study_design.evidence_ids = []

    warnings = _validate_extraction(
        extraction,
        {"E1": {}, "E2": {}, "E3": {}},
    )

    assert any("no evidence citation" in item for item in warnings)


def test_duplicate_evidence_ids_are_removed():
    extraction = make_extraction()
    extraction.study_design.evidence_ids = ["E1", "E1"]

    _validate_extraction(
        extraction,
        {"E1": {}, "E2": {}, "E3": {}},
    )

    assert extraction.study_design.evidence_ids == ["E1"]


def test_not_reported_field_has_no_citation():
    extraction = make_extraction()
    extraction.sample_size = make_field(        
        "Not reported in retrieved evidence",
        [],
        "not_reported",
    )

    warnings = _validate_extraction(
        extraction,
        {"E1": {}, "E2": {}, "E3": {}},
    )

    assert not any("sample_size" in item for item in warnings)


def test_invalid_model_citation_is_corrected_with_one_retry(monkeypatch):
    from app.services import evidence_extractor

    extraction = make_extraction()
    responses = [
        {
            **extraction.model_dump(),
            "study_design": {
                "value": "Randomized controlled trial",
                "evidence_ids": ["E9"],
                "status": "reported",
            },
        },
        extraction.model_dump(),
    ]
    prompts = []

    monkeypatch.setattr(
        evidence_extractor,
        "retrieve_evidence",
        lambda **kwargs: [
            {
                "text": "Study passage one.",
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "filename": "study.pdf",
                "page_start": 1,
                "page_end": 1,
            },
            {
                "text": "Study passage two.",
                "chunk_id": "chunk-2",
                "document_id": "doc-1",
                "filename": "study.pdf",
                "page_start": 2,
                "page_end": 2,
            },
            {
                "text": "Study passage three.",
                "chunk_id": "chunk-3",
                "document_id": "doc-1",
                "filename": "study.pdf",
                "page_start": 3,
                "page_end": 3,
            },
        ],
    )

    def fake_generate_json(**kwargs):
        prompts.append(kwargs["user_prompt"])
        return responses.pop(0)

    monkeypatch.setattr(evidence_extractor, "generate_json", fake_generate_json)

    result, citations, warnings = extract_study_evidence(
        project_id="1",
        query="What study design is reported?",
        top_k=2,
        document_ids=["doc-1"],
    )

    assert result.study_design.evidence_ids == ["E1"]
    assert {citation["evidence_id"] for citation in citations} == {
        "E1",
        "E2",
        "E3",
    }
    assert len(prompts) == 2
    assert "only valid evidence IDs are: E1, E2, E3" in prompts[1]
    assert warnings


def test_persistent_invalid_citation_is_uncertain_not_fabricated(monkeypatch):
    from app.services import evidence_extractor

    extraction = make_extraction()
    invalid_response = {
        **extraction.model_dump(),
        "study_design": {
            "value": "Randomized controlled trial",
            "evidence_ids": ["E9"],
            "status": "reported",
        },
    }
    monkeypatch.setattr(
        evidence_extractor,
        "retrieve_evidence",
        lambda **kwargs: [
            {
                "text": "Passage supporting other reported fields.",
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "filename": "study.pdf",
                "page_start": 1,
                "page_end": 1,
            },
            {
                "text": "Another supplied passage.",
                "chunk_id": "chunk-2",
                "document_id": "doc-1",
                "filename": "study.pdf",
                "page_start": 2,
                "page_end": 2,
            },
            {
                "text": "A third supplied passage.",
                "chunk_id": "chunk-3",
                "document_id": "doc-1",
                "filename": "study.pdf",
                "page_start": 3,
                "page_end": 3,
            },
        ],
    )
    monkeypatch.setattr(
        evidence_extractor,
        "generate_json",
        lambda **kwargs: invalid_response,
    )

    result, citations, warnings = extract_study_evidence(
        project_id="1",
        query="What study design is reported?",
        top_k=3,
        document_ids=["doc-1"],
    )

    assert result.study_design.value == "Randomized controlled trial"
    assert result.study_design.status == "uncertain"
    assert result.study_design.evidence_ids == []
    assert all(citation["evidence_id"] != "E9" for citation in citations)
    assert any("marked uncertain" in warning for warning in warnings)