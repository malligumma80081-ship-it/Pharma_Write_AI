import os
from pathlib import Path
from typing import TypedDict, cast

import chromadb
import numpy as np
from chromadb.api.types import (
    Metadata,
    Where,
)

from app.services.chunking import TextChunk
from app.services.embeddings import embed_query, embed_texts


CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERSIST_DIRECTORY = PROJECT_ROOT / CHROMA_PATH
PERSIST_DIRECTORY.mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(path=str(PERSIST_DIRECTORY))
collection = client.get_or_create_collection(
    name="pharmawrite_evidence",
    metadata={"hnsw:space": "cosine"},
)


class RetrievedChunk(TypedDict):
    chunk_id: str
    text: str
    filename: str
    document_id: str
    project_id: str
    page_start: int
    page_end: int
    chunk_index: int
    distance: float


class StoredChunk(TypedDict):
    chunk_id: str
    text: str
    metadata: Metadata


def index_chunks(
    chunks: list[TextChunk],
    document_id: str,
    project_id: str,
    filename: str,
) -> int:
    """Upsert document chunks and their embeddings into ChromaDB."""
    if not chunks:
        raise ValueError("There are no chunks to index.")

    texts = [chunk.text for chunk in chunks]
    if any(not text.strip() for text in texts):
        raise ValueError("Chunks to index cannot contain empty text.")

    vectors = np.asarray(embed_texts(texts), dtype=np.float32)
    if len(vectors) != len(chunks):
        raise RuntimeError(
            "The embedding service returned a different number of vectors "
            "than the number of chunks."
        )

    ids = [
        f"{document_id}_{chunk.chunk_index}"
        for chunk in chunks
    ]
    metadatas: list[Metadata] = [
        {
            "document_id": document_id,
            "project_id": project_id,
            "filename": filename,
            "chunk_index": chunk.chunk_index,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }
        for chunk in chunks
    ]

    existing = collection.get(
        where={"document_id": document_id},
        include=[],
    )
    stale_ids = [
        chunk_id
        for chunk_id in existing["ids"]
        if chunk_id not in ids
    ]

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=vectors,
        metadatas=metadatas,
    )

    if stale_ids:
        collection.delete(ids=stale_ids)

    return len(ids)


def search_chunks(
    query: str,
    project_id: str,
    top_k: int = 5,
    document_ids: list[str] | None = None,
    page_from: int | None = None,
    page_to: int | None = None,
) -> list[RetrievedChunk]:
    """Search within one project, optionally filtering documents and pages."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")

    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")

    if page_from is not None and page_from < 1:
        raise ValueError("page_from must be at least 1.")

    if page_to is not None and page_to < 1:
        raise ValueError("page_to must be at least 1.")

    if (
        page_from is not None
        and page_to is not None
        and page_from > page_to
    ):
        raise ValueError("page_from cannot exceed page_to.")

    if document_ids is not None and not document_ids:
        return []

    conditions: list[Where] = [{"project_id": project_id}]

    if document_ids is not None:
        conditions.append(
            cast(
                Where,
                {"document_id": {"$in": list(document_ids)}},
            )
        )

    if page_from is not None:
        conditions.append({"page_end": {"$gte": page_from}})

    if page_to is not None:
        conditions.append({"page_start": {"$lte": page_to}})

    where_filter: Where = (
        conditions[0]
        if len(conditions) == 1
        else {"$and": conditions}
    )

    result = collection.query(
        query_embeddings=[embed_query(query)],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    ids = result["ids"][0]
    documents = result["documents"]
    metadatas = result["metadatas"]
    distances = result["distances"]

    if documents is None or metadatas is None or distances is None:
        raise RuntimeError(
            "ChromaDB did not return the requested chunk fields."
        )

    document_batch = documents[0]
    metadata_batch = metadatas[0]
    distance_batch = distances[0]
    if not (
        len(ids)
        == len(document_batch)
        == len(metadata_batch)
        == len(distance_batch)
    ):
        raise RuntimeError("ChromaDB returned mismatched search result fields.")

    matches: list[RetrievedChunk] = []
    for chunk_id, text, metadata, distance in zip(
        ids,
        document_batch,
        metadata_batch,
        distance_batch,
        strict=True,
    ):
        if metadata is None:
            raise RuntimeError(
                f"ChromaDB returned no metadata for chunk {chunk_id}."
            )

        filename = metadata.get("filename")
        document_id = metadata.get("document_id")
        metadata_project_id = metadata.get("project_id")
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        chunk_index = metadata.get("chunk_index")
        if (
            not isinstance(filename, str)
            or not isinstance(document_id, str)
            or not isinstance(metadata_project_id, str)
        ):
            raise RuntimeError(
                f"ChromaDB returned invalid identity metadata for {chunk_id}."
            )
        if (
            not isinstance(page_start, int)
            or isinstance(page_start, bool)
            or not isinstance(page_end, int)
            or isinstance(page_end, bool)
            or not isinstance(chunk_index, int)
            or isinstance(chunk_index, bool)
        ):
            raise RuntimeError(
                f"ChromaDB returned invalid page metadata for {chunk_id}."
            )

        matches.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "filename": filename,
                "document_id": document_id,
                "project_id": metadata_project_id,
                "page_start": page_start,
                "page_end": page_end,
                "chunk_index": chunk_index,
                "distance": float(distance),
            }
        )

    return matches


def delete_document_chunks(document_id: str) -> None:
    """Delete indexed chunks for a document."""
    collection.delete(where={"document_id": document_id})


def get_chunk_by_id(chunk_id: str) -> StoredChunk | None:
    """Return the exact indexed chunk and metadata, or None if not found."""
    result = collection.get(
        ids=[chunk_id],
        include=["documents", "metadatas"],
    )

    if not result["ids"]:
        return None

    documents = result["documents"]
    metadatas = result["metadatas"]
    if documents is None or metadatas is None:
        raise RuntimeError(
            "ChromaDB did not return the requested chunk fields."
        )

    text = documents[0]
    metadata = metadatas[0]
    if text is None or metadata is None:
        raise RuntimeError(
            f"ChromaDB returned incomplete data for chunk {chunk_id}."
        )

    return {
        "chunk_id": result["ids"][0],
        "text": text,
        "metadata": metadata,
    }

