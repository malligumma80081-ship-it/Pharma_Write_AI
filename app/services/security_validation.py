from typing import Any


def validate_evidence_ids(
    returned_ids: list[str],
    allowed_ids: set[str],
) -> None:
    """Reject evidence references that were not provided to the model."""
    if not set(returned_ids).issubset(allowed_ids):
        raise ValueError(
            "Model output contains an unknown evidence ID."
        )


def validate_generated_text(
    value: Any,
    max_length: int = 20_000,
) -> str:
    """Check basic output shape and size before displaying or saving."""
    if not isinstance(value, str):
        raise ValueError("Generated text must be a string.")

    if len(value) > max_length:
        raise ValueError("Generated text exceeds the allowed limit.")

    if not value.strip():
        raise ValueError("Generated text is empty.")

    return value.strip()