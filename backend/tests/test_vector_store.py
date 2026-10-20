"""Tests for the vector store, on a real embedded Chroma in a temporary folder.

Vectors are written by hand (3 dimensions), so no embedding model is needed.
"""

from pathlib import Path

import pytest

from app.retrieval.vector_store import (
    ChromaVectorStore,
    VectorRecord,
    VectorStoreError,
    collection_name_for,
)

MODEL = "test-embedding-model"


def record(
    record_id: str, embedding: list[float], document_id: str = "doc-1", page: int = 1
) -> VectorRecord:
    return VectorRecord(
        id=record_id, embedding=embedding, document_id=document_id, page_number=page, position=0
    )


@pytest.fixture
def store(tmp_path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(tmp_path / "chroma", MODEL)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("nomic-embed-text", "chunks_nomic-embed-text"),
        ("nomic-embed-text:latest", "chunks_nomic-embed-text-latest"),
        ("openai/text-embedding-3-small", "chunks_openai-text-embedding-3-small"),
    ],
)
def test_collection_name_is_valid_for_chroma(model: str, expected: str) -> None:
    assert collection_name_for(model) == expected


def test_collection_name_refuses_a_model_name_without_letters() -> None:
    with pytest.raises(ValueError):
        collection_name_for("///")


def test_query_returns_the_closest_records_first(store: ChromaVectorStore) -> None:
    store.upsert(
        [
            record("far", [0.0, 1.0, 0.0], page=3),
            record("exact", [1.0, 0.0, 0.0], page=1),
            record("close", [0.9, 0.1, 0.0], page=2),
        ]
    )

    matches = store.query([1.0, 0.0, 0.0], top_k=2)

    assert [match.id for match in matches] == ["exact", "close"]
    assert matches[0].score == pytest.approx(1.0, abs=1e-5)
    assert matches[0].score > matches[1].score
    assert (matches[0].document_id, matches[0].page_number, matches[0].position) == (
        "doc-1",
        1,
        0,
    )


def test_query_can_be_limited_to_some_documents(store: ChromaVectorStore) -> None:
    store.upsert(
        [
            record("contract", [1.0, 0.0, 0.0], document_id="contract"),
            record("invoice", [1.0, 0.0, 0.0], document_id="invoice"),
        ]
    )

    matches = store.query([1.0, 0.0, 0.0], top_k=5, document_ids=["invoice"])

    assert [match.id for match in matches] == ["invoice"]


def test_query_with_an_empty_document_list_returns_nothing(store: ChromaVectorStore) -> None:
    store.upsert([record("a", [1.0, 0.0, 0.0])])
    assert store.query([1.0, 0.0, 0.0], top_k=5, document_ids=[]) == []


def test_query_on_an_empty_store_returns_nothing(store: ChromaVectorStore) -> None:
    assert store.query([1.0, 0.0, 0.0], top_k=5) == []


def test_top_k_larger_than_the_store_returns_every_record(store: ChromaVectorStore) -> None:
    store.upsert([record("a", [1.0, 0.0, 0.0]), record("b", [0.0, 1.0, 0.0])])
    assert len(store.query([1.0, 0.0, 0.0], top_k=10)) == 2


def test_top_k_must_be_positive(store: ChromaVectorStore) -> None:
    with pytest.raises(ValueError):
        store.query([1.0, 0.0, 0.0], top_k=0)


def test_upsert_replaces_a_record_with_the_same_id(store: ChromaVectorStore) -> None:
    store.upsert([record("a", [1.0, 0.0, 0.0], page=1)])
    store.upsert([record("a", [0.0, 1.0, 0.0], page=7)])

    matches = store.query([0.0, 1.0, 0.0], top_k=1)

    assert store.count() == 1
    assert matches[0].page_number == 7


def test_upsert_with_no_record_does_nothing(store: ChromaVectorStore) -> None:
    store.upsert([])
    assert store.count() == 0


def test_delete_document_removes_only_that_document(store: ChromaVectorStore) -> None:
    store.upsert(
        [
            record("c1", [1.0, 0.0, 0.0], document_id="contract"),
            record("c2", [0.0, 1.0, 0.0], document_id="contract"),
            record("i1", [0.0, 0.0, 1.0], document_id="invoice"),
        ]
    )

    store.delete_document("contract")
    store.delete_document("unknown-document")

    assert store.count() == 1
    assert [match.id for match in store.query([1.0, 0.0, 0.0], top_k=5)] == ["i1"]


def test_a_vector_with_the_wrong_dimension_is_refused(store: ChromaVectorStore) -> None:
    store.upsert([record("a", [1.0, 0.0, 0.0])])
    with pytest.raises(VectorStoreError):
        store.upsert([record("b", [1.0, 0.0])])


def test_data_survives_reopening_the_store(tmp_path: Path) -> None:
    ChromaVectorStore(tmp_path / "chroma", MODEL).upsert([record("a", [1.0, 0.0, 0.0])])

    reopened = ChromaVectorStore(tmp_path / "chroma", MODEL)

    assert reopened.count() == 1


def test_each_embedding_model_has_its_own_collection(tmp_path: Path) -> None:
    ChromaVectorStore(tmp_path / "chroma", "model-a").upsert([record("a", [1.0, 0.0, 0.0])])

    other = ChromaVectorStore(tmp_path / "chroma", "model-b")

    assert other.count() == 0


def test_two_models_with_the_same_cleaned_name_are_not_mixed(tmp_path: Path) -> None:
    ChromaVectorStore(tmp_path / "chroma", "provider/model")
    with pytest.raises(VectorStoreError, match="Re-index"):
        ChromaVectorStore(tmp_path / "chroma", "provider-model")