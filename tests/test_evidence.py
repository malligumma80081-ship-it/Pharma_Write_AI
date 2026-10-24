import pytest

from app.schemas.evidence import (
    EvidenceField,
    StudyEvidenceExtraction,
)
from app.services.evidence_extractor import (
    EvidenceCitationError,
    _validate_extraction,
)


def make_field(value="Example", ids=None, status="reported"):
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