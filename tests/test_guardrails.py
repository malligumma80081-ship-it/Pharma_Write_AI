import pytest

from app.services.guardrails import (
    validate_evidence_ids,
    validate_generated_text,
)


def test_evidence_ids_from_allowed_set_are_accepted():
    validate_evidence_ids(["E1", "E2"], {"E1", "E2", "E3"})


def test_unknown_evidence_id_is_rejected():
    with pytest.raises(ValueError, match="unknown evidence ID"):
        validate_evidence_ids(["E1", "E99"], {"E1", "E2"})


def test_empty_generated_text_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_generated_text("  \n")


def test_oversized_generated_text_is_rejected():
    with pytest.raises(ValueError, match="allowed limit"):
        validate_generated_text("A" * 101, max_length=100)


def test_non_string_generated_text_is_rejected():
    with pytest.raises(ValueError, match="must be a string"):
        validate_generated_text(None)


def test_valid_generated_text_is_trimmed():
    assert validate_generated_text("  Evidence summary\n") == "Evidence summary"
