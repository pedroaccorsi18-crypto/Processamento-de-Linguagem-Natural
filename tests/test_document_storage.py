from __future__ import annotations

import pytest

from synapse_ai.services.document_service import UploadedDocument
from synapse_ai.services.document_storage import (
    DocumentStorageError,
    build_document_storage_path,
    download_original_document,
    upload_original_document,
)


class FakeBucket:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.fail_once = False
        self.upload_call: dict[str, object] = {}
        self.upload_calls: list[dict[str, object]] = []

    def upload(
        self,
        path: str,
        content: bytes,
        options: dict[str, str],
    ) -> None:
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("failed once")
        if self.fail:
            raise RuntimeError("failed")
        self.upload_call = {"path": path, "content": content, "options": options}
        self.upload_calls.append(self.upload_call)

    def download(self, path: str) -> bytes:
        if self.fail:
            raise RuntimeError("failed")
        return f"downloaded:{path}".encode()


class FakeStorage:
    def __init__(self, bucket: FakeBucket) -> None:
        self.bucket = bucket
        self.bucket_name = ""

    def from_(self, bucket_name: str) -> FakeBucket:
        self.bucket_name = bucket_name
        return self.bucket


class FakeClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.storage = FakeStorage(bucket)


def test_build_document_storage_path_sanitizes_filename() -> None:
    assert (
        build_document_storage_path("user-1", "doc-1", "../Ata Reuniao.pdf")
        == "user-1/doc-1/Ata_Reuniao.pdf"
    )


def test_upload_original_document_uses_private_user_path() -> None:
    bucket = FakeBucket()
    client = FakeClient(bucket)
    upload = UploadedDocument(
        filename="ata.pdf",
        content_type="application/pdf",
        content=b"pdf",
    )

    stored_file = upload_original_document(client, "user-1", "doc-1", upload)

    assert stored_file.bucket == "documents"
    assert stored_file.path == "user-1/doc-1/ata.pdf"
    assert bucket.upload_call["content"] == b"pdf"
    assert bucket.upload_call["options"]["content-type"] == "application/pdf"


def test_upload_original_document_falls_back_to_binary_content_type() -> None:
    bucket = FakeBucket()
    bucket.fail_once = True
    client = FakeClient(bucket)
    upload = UploadedDocument(
        filename="entrevista.m4a",
        content_type="audio/x-m4a",
        content=b"audio",
    )

    stored_file = upload_original_document(client, "user-1", "doc-1", upload)

    assert stored_file.path == "user-1/doc-1/entrevista.m4a"
    assert bucket.upload_call["options"]["content-type"] == "application/octet-stream"


def test_download_original_document_returns_bytes() -> None:
    client = FakeClient(FakeBucket())

    assert download_original_document(client, "documents", "user-1/doc-1/ata.pdf") == (
        b"downloaded:user-1/doc-1/ata.pdf"
    )


def test_upload_original_document_wraps_errors() -> None:
    client = FakeClient(FakeBucket(fail=True))
    upload = UploadedDocument("ata.pdf", "application/pdf", b"pdf")

    with pytest.raises(DocumentStorageError):
        upload_original_document(client, "user-1", "doc-1", upload)
