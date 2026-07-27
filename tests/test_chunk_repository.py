from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from synapse_ai.services.chunk_repository import (
    ChunkPersistenceError,
    list_document_chunk_counts,
    list_document_chunks_by_references,
    match_document_chunks,
    replace_document_chunks,
)
from synapse_ai.services.chunking_service import TextChunk


class FakeTableQuery:
    def __init__(
        self,
        fail: bool = False,
        response_data: list[dict[str, Any]] | None = None,
    ) -> None:
        self.fail = fail
        self.response_data = response_data if response_data is not None else []
        self.inserted_payload: list[dict[str, Any]] = []
        self.deleted_document_id: str | None = None
        self.filters: dict[str, Any] = {}

    def delete(self) -> FakeTableQuery:
        return self

    def insert(self, payload: list[dict[str, Any]]) -> FakeTableQuery:
        self.inserted_payload = payload
        return self

    def select(self, _columns: str) -> FakeTableQuery:
        return self

    def eq(self, column: str, value: str) -> FakeTableQuery:
        self.filters[column] = value
        if column == "document_id":
            self.deleted_document_id = value
        return self

    def in_(self, column: str, values: list[str]) -> FakeTableQuery:
        self.filters[column] = values
        return self

    def execute(self) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("failed")
        if self.inserted_payload:
            return SimpleNamespace(data=self.inserted_payload)
        return SimpleNamespace(data=self.response_data)


class FakeRpcQuery:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(
        self,
        table_query: FakeTableQuery,
        rpc_data: list[dict[str, Any]] | None = None,
    ) -> None:
        self.table_query = table_query
        self.rpc_data = rpc_data if rpc_data is not None else []
        self.rpc_call: dict[str, Any] = {}

    def table(self, table_name: str) -> FakeTableQuery:
        assert table_name == "document_chunks"
        return self.table_query

    def rpc(self, function_name: str, params: dict[str, Any]) -> FakeRpcQuery:
        self.rpc_call = {"function_name": function_name, "params": params}
        return FakeRpcQuery(self.rpc_data)


def test_replace_document_chunks_recreates_chunks() -> None:
    query = FakeTableQuery()
    client = FakeClient(query)

    count = replace_document_chunks(
        client,
        "user-1",
        "doc-1",
        "ata.txt",
        [TextChunk(index=0, content="texto", char_count=5)],
        [[0.1, 0.2]],
        "text-embedding-3-small",
    )

    assert count == 1
    assert query.deleted_document_id == "doc-1"
    assert query.inserted_payload[0]["embedding"] == [0.1, 0.2]
    assert query.inserted_payload[0]["metadata"] == {"filename": "ata.txt"}


def test_replace_document_chunks_rejects_mismatched_embeddings() -> None:
    with pytest.raises(ChunkPersistenceError):
        replace_document_chunks(
            FakeClient(FakeTableQuery()),
            "user-1",
            "doc-1",
            "ata.txt",
            [TextChunk(index=0, content="texto", char_count=5)],
            [],
            "text-embedding-3-small",
        )


def test_match_document_chunks_calls_rpc() -> None:
    expected = [{"document_id": "doc-1", "content": "texto"}]
    client = FakeClient(FakeTableQuery(), expected)

    matches = match_document_chunks(client, "user-1", [0.1, 0.2], limit=3)

    assert matches == expected
    assert client.rpc_call["function_name"] == "match_document_chunks"
    assert client.rpc_call["params"]["match_count"] == 3


def test_match_document_chunks_filters_selected_documents() -> None:
    client = FakeClient(FakeTableQuery(), [])

    match_document_chunks(client, "user-1", [0.1, 0.2], document_ids=["doc-1", "doc-2"])

    assert client.rpc_call["function_name"] == "match_document_chunks_in_documents"
    assert client.rpc_call["params"]["filter_document_ids"] == ["doc-1", "doc-2"]


def test_list_document_chunk_counts_groups_rows_by_document() -> None:
    query = FakeTableQuery(
        response_data=[
            {"document_id": "doc-1"},
            {"document_id": "doc-1"},
            {"document_id": "doc-2"},
        ]
    )
    client = FakeClient(query)

    counts = list_document_chunk_counts(
        client,
        "user-1",
        ["doc-1", "doc-2"],
        "text-embedding-3-small",
    )

    assert counts == {"doc-1": 2, "doc-2": 1}
    assert query.filters["user_id"] == "user-1"
    assert query.filters["embedding_model"] == "text-embedding-3-small"
    assert query.filters["document_id"] == ["doc-1", "doc-2"]


def test_list_document_chunks_by_references_returns_matching_chunks() -> None:
    query = FakeTableQuery(
        response_data=[
            {"document_id": "doc-1", "chunk_index": 0, "content": "Fonte usada."},
            {"document_id": "doc-1", "chunk_index": 2, "content": "Outra fonte."},
            {"document_id": "doc-2", "chunk_index": 0, "content": "Ignorada."},
        ]
    )
    client = FakeClient(query)

    chunks = list_document_chunks_by_references(
        client,
        "user-1",
        [("doc-1", 0), ("doc-1", 2)],
    )

    assert chunks[("doc-1", 0)]["content"] == "Fonte usada."
    assert chunks[("doc-1", 2)]["content"] == "Outra fonte."
    assert ("doc-2", 0) not in chunks
    assert query.filters["user_id"] == "user-1"
    assert query.filters["document_id"] == ["doc-1"]
