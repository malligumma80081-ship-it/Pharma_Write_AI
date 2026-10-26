from app.services import knowledge_base


def evidence_item(
    chunk_id="chunk-1",
    filename="study.pdf",
    page_start=4,
    page_end=4,
):
    return {
        "chunk_id": chunk_id,
        "text": "The study included 120 participants.",
        "filename": filename,
        "document_id": "document-1",
        "project_id": "7",
        "page_start": page_start,
        "page_end": page_end,
        "chunk_index": 0,
        "distance": 0.12,
    }


def test_answer_uses_only_valid_model_citations(monkeypatch):
    monkeypatch.setattr(
        knowledge_base,
        "retrieve_evidence",
        lambda **kwargs: [evidence_item()],
    )
    monkeypatch.setattr(
        knowledge_base,
        "generate_json",
        lambda **kwargs: {
            "answerable": True,
            "answer": "The study included 120 participants.",
            "evidence_ids": ["E1"],
        },
    )

    answer, citations = knowledge_base.answer_knowledge_question(
        project_id="7",
        query="How many participants were included?",
    )

    assert answer == "The study included 120 participants."
    assert [citation.evidence_id for citation in citations] == ["E1"]
    assert citations[0].filename == "study.pdf"
    assert citations[0].page_start == 4
    assert citations[0].quote == "The study included 120 participants."


def test_answer_abstains_if_model_citation_remains_invalid(monkeypatch):
    calls = []
    monkeypatch.setattr(
        knowledge_base,
        "retrieve_evidence",
        lambda **kwargs: [evidence_item()],
    )

    def invalid_model_response(**kwargs):
        calls.append(kwargs)
        return {
            "answerable": True,
            "answer": "Unverified answer.",
            "evidence_ids": ["E99"],
        }

    monkeypatch.setattr(
        knowledge_base,
        "generate_json",
        invalid_model_response,
    )

    answer, citations = knowledge_base.answer_knowledge_question(
        project_id="7",
        query="What did this study report?",
    )

    assert answer == knowledge_base.VALIDATION_FAILURE
    assert citations == []
    assert len(calls) == 2
    assert "cite only these IDs: E1" in calls[1]["user_prompt"]


def test_answer_abstains_without_retrieved_passages(monkeypatch):
    monkeypatch.setattr(
        knowledge_base,
        "retrieve_evidence",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        knowledge_base,
        "generate_json",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Model must not be asked without evidence.")
        ),
    )

    answer, citations = knowledge_base.answer_knowledge_question(
        project_id="7",
        query="What is the primary outcome?",
    )

    assert answer == knowledge_base.ABSTENTION
    assert citations == []
