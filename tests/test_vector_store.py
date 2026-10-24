import pytest

from app.services import vector_store
from app.services.chunking import TextChunk


class FakeCollection:
    def __init__(self):
        self.upsert_args = None
        self.deleted_ids = None
        self.query_args = None

    def get(self, **kwargs):
        assert kwargs == {
            "where": {"document_id": "doc-1"},
            "include": [],
        }
        return {"ids": ["doc-1_0", "doc-1_1", "doc-1_2"]}

    def upsert(self, **kwargs):
        self.upsert_args = kwargs

    def delete(self, **kwargs):
        self.deleted_ids = kwargs["ids"]

    def query(self, **kwargs):
        self.query_args = kwargs
        return {
            "ids": [["doc-1_0"]],
            "documents": [["evidence text"]],
            "metadatas": [
                [
                    {
                        "document_id": "doc-1",
                        "project_id": "7",
                        "filename": "study.pdf",
                        "chunk_index": 0,
                        "page_start": 2,
                        "page_end": 3,
                    }
                ]
            ],
            "distances": [[0.12]],
        }


def test_index_replaces_chunks_and_removes_stale_ids(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(vector_store, "collection", fake_collection)
    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        lambda texts: [[0.1, 0.2] for _ in texts],
    )
    chunks = [
        TextChunk(
            chunk_index=0,
            text="first chunk",
            page_start=1,
            page_end=1,
        ),
        TextChunk(
            chunk_index=1,
            text="second chunk",
            page_start=2,
            page_end=2,
        ),
    ]

    indexed_count = vector_store.index_chunks(
        chunks,
        document_id="doc-1",
        project_id="7",
        filename="study.pdf",
    )

    assert indexed_count == 2
    assert fake_collection.upsert_args["ids"] == ["doc-1_0", "doc-1_1"]
    assert fake_collection.deleted_ids == ["doc-1_2"]


def test_index_rejects_empty_chunk_text(monkeypatch):
    monkeypatch.setattr(vector_store, "collection", FakeCollection())

    with pytest.raises(ValueError, match="cannot contain empty text"):
        vector_store.index_chunks(
            [
                TextChunk(
                    chunk_index=0,
                    text="  ",
                    page_start=1,
                    page_end=1,
                )
            ],
            document_id="doc-1",
            project_id="7",
            filename="study.pdf",
        )


def test_search_builds_page_overlap_filter_and_normalizes_result(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(vector_store, "collection", fake_collection)
    monkeypatch.setattr(vector_store, "embed_query", lambda query: [0.3, 0.4])

    results = vector_store.search_chunks(
        query="study outcomes",
        project_id="7",
        document_ids=["doc-1"],
        page_from=3,
        page_to=4,
    )

    assert fake_collection.query_args["where"] == {
        "$and": [
            {"project_id": "7"},
            {"document_id": {"$in": ["doc-1"]}},
            {"page_end": {"$gte": 3}},
            {"page_start": {"$lte": 4}},
        ]
    }
    assert results == [
        {
            "chunk_id": "doc-1_0",
            "text": "evidence text",
            "filename": "study.pdf",
            "document_id": "doc-1",
            "project_id": "7",
            "page_start": 2,
            "page_end": 3,
            "chunk_index": 0,
            "distance": 0.12,
        }
    ]


def test_search_returns_empty_for_explicitly_empty_document_filter(
    monkeypatch,
):
    fake_collection = FakeCollection()
    monkeypatch.setattr(vector_store, "collection", fake_collection)

    assert vector_store.search_chunks(
        query="study outcomes",
        project_id="7",
        document_ids=[],
    ) == []
    assert fake_collection.query_args is None


def test_search_rejects_invalid_page_range():
    with pytest.raises(ValueError, match="page_from cannot exceed page_to"):
        vector_store.search_chunks(
            query="study outcomes",
            project_id="7",
            page_from=5,
            page_to=3,
        )
