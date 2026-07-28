from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from synapse_ai.services.document_repository import (
    DocumentPersistenceError,
    list_user_documents,
    save_parsed_document,
    update_document_storage_location,
)
from synapse_ai.services.document_service import UploadedDocument, parse_uploaded_document


class FakeQuery:
    def __init__(self, response_data: Any | None = None, fail: bool = False) -> None:
        self.response_data = response_data if response_data is not None else []
        self.fail = fail
        self.inserted_payload: dict[str, Any] | None = None
        self.selected_columns = ""
        self.filters: dict[str, str] = {}

    def insert(self, payload: dict[str, Any]) -> FakeQuery:
        self.inserted_payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> FakeQuery:
        self.inserted_payload = payload
        return self

    def select(self, columns: str) -> FakeQuery:
        self.selected_columns = columns
        return self

    def eq(self, column: str, value: str) -> FakeQuery:
        self.filters[column] = value
        return self

    def order(self, _column: str, desc: bool = False) -> FakeQuery:
        return self

    def limit(self, _limit: int) -> FakeQuery:
        return self

    def execute(self) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("failed")
        if self.inserted_payload is not None:
            return SimpleNamespace(data=[self.inserted_payload])
        return SimpleNamespace(data=self.response_data)


class FakeClient:
    def __init__(self, query: FakeQuery) -> None:
        self.query = query

    def table(self, table_name: str) -> FakeQuery:
        assert table_name == "documents"
        return self.query


def test_save_parsed_document_uses_documents_table() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    parsed = parse_uploaded_document(
        UploadedDocument(filename="ata.txt", content_type="text/plain", content=b"texto")
    )

    record = save_parsed_document(client, "user-1", parsed)

    assert record["user_id"] == "user-1"
    assert record["filename"] == "ata.txt"
    assert record["extracted_text"] == "texto"


def test_save_parsed_document_wraps_errors() -> None:
    client = FakeClient(FakeQuery(fail=True))
    parsed = parse_uploaded_document(
        UploadedDocument(filename="ata.txt", content_type="text/plain", content=b"texto")
    )

    with pytest.raises(DocumentPersistenceError):
        save_parsed_document(client, "user-1", parsed)


def test_list_user_documents_returns_response_data() -> None:
    documents = [{"id": "doc-1", "filename": "ata.txt"}]
    query = FakeQuery(response_data=documents)
    client = FakeClient(query)

    assert list_user_documents(client, "user-1") == documents
    assert "user_id" in query.selected_columns
    assert query.filters["user_id"] == "user-1"


def test_update_document_storage_location_updates_documents_table() -> None:
    query = FakeQuery()
    client = FakeClient(query)

    update_document_storage_location(
        client,
        "user-1",
        "doc-1",
        "documents",
        "user-1/doc-1/ata.txt",
    )

    assert query.inserted_payload == {
        "storage_bucket": "documents",
        "storage_path": "user-1/doc-1/ata.txt",
    }
