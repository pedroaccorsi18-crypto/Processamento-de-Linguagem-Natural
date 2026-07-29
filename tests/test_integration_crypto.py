from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from synapse_ai.services.integration_crypto import (
    IntegrationCredentialError,
    decrypt_integration_credentials,
    encrypt_integration_credentials,
)


def test_credentials_are_encrypted_and_recovered_with_the_same_key() -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")

    encrypted = encrypt_integration_credentials(
        {"access_token": "access-secret", "refresh_token": "refresh-secret"},
        encryption_key,
    )

    assert "access-secret" not in encrypted
    assert decrypt_integration_credentials(encrypted, encryption_key) == {
        "access_token": "access-secret",
        "refresh_token": "refresh-secret",
    }


def test_credentials_reject_an_invalid_or_missing_key() -> None:
    with pytest.raises(IntegrationCredentialError):
        encrypt_integration_credentials({"access_token": "secret"}, "")

    with pytest.raises(IntegrationCredentialError):
        encrypt_integration_credentials({"access_token": "secret"}, "invalid-key")
