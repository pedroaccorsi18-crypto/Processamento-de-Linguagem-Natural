from __future__ import annotations

from synapse_ai.ui.upload_page import _find_duplicate_document


def test_find_duplicate_document_matches_only_current_user() -> None:
    parsed_metadata = {"checksum_sha256": "same-checksum"}
    documents = [
        {
            "filename": "arquivo-de-outra-conta.pdf",
            "user_id": "user-2",
            "metadata": {"checksum_sha256": "same-checksum"},
        },
        {
            "filename": "arquivo-da-conta-atual.pdf",
            "user_id": "user-1",
            "metadata": {"checksum_sha256": "same-checksum"},
        },
    ]

    duplicate = _find_duplicate_document(parsed_metadata, documents, "user-1")

    assert duplicate is not None
    assert duplicate["filename"] == "arquivo-da-conta-atual.pdf"


def test_find_duplicate_document_ignores_other_users() -> None:
    parsed_metadata = {"checksum_sha256": "same-checksum"}
    documents = [
        {
            "filename": "arquivo-de-outra-conta.pdf",
            "user_id": "user-2",
            "metadata": {"checksum_sha256": "same-checksum"},
        }
    ]

    assert _find_duplicate_document(parsed_metadata, documents, "user-1") is None


def test_find_duplicate_document_ignores_records_without_user_id() -> None:
    parsed_metadata = {"checksum_sha256": "same-checksum"}
    documents = [
        {
            "filename": "registro-antigo-sem-dono.pdf",
            "metadata": {"checksum_sha256": "same-checksum"},
        }
    ]

    assert _find_duplicate_document(parsed_metadata, documents, "user-1") is None
