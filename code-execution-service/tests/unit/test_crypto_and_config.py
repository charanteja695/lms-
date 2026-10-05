import base64

import pytest
from cryptography.fernet import Fernet

from app.core.config import DEV_ENCRYPTION_KEY, DEV_SECRET_MARKER, Settings
from app.core.crypto import DecryptionError, SecretCipher

KEY_OLD = Fernet.generate_key().decode()
KEY_NEW = Fernet.generate_key().decode()


def test_round_trip_and_ciphertext_reveals_nothing() -> None:
    cipher = SecretCipher([KEY_NEW])
    token = cipher.encrypt("secret input 1 2 3")
    assert "secret" not in token
    assert cipher.decrypt(token) == "secret input 1 2 3"
    assert cipher.encrypt("x") != cipher.encrypt("x")  # never the same ciphertext twice


def test_key_rotation_keeps_old_data_readable_then_retires_the_old_key() -> None:
    old_token = SecretCipher([KEY_OLD]).encrypt("hidden expected output")
    rotating = SecretCipher([KEY_NEW, KEY_OLD])  # newest first
    assert rotating.decrypt(old_token) == "hidden expected output"

    rotated = rotating.rotate(old_token)
    assert SecretCipher([KEY_NEW]).decrypt(rotated) == "hidden expected output"  # now the old key is not needed
    with pytest.raises(DecryptionError):
        SecretCipher([KEY_NEW]).decrypt(old_token)


def test_a_wrong_key_is_a_clear_error_not_garbage() -> None:
    token = SecretCipher([KEY_OLD]).encrypt("data")
    with pytest.raises(DecryptionError):
        SecretCipher([KEY_NEW]).decrypt(token)


def _production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "ENVIRONMENT": "production",
        "EXECUTION_ENGINE": "judge0",
        "TRUSTED_HOSTS": ["code.example.com"],
        "INTERNAL_SERVICE_TOKEN": "a-long-random-production-token",
        "TEST_CASE_ENCRYPTION_KEYS": KEY_NEW,
        "USER_MANAGEMENT_JWKS_URL": "https://auth.example.com/.well-known/jwks.json",
    }
    values.update(overrides)
    return Settings(**values)


def test_a_correct_production_configuration_is_accepted() -> None:
    _production().validate_security()


@pytest.mark.parametrize(
    ("override", "complaint"),
    [
        ({"EXECUTION_ENGINE": "local"}, "EXECUTION_ENGINE=local"),  # code without isolation
        ({"TEST_CASE_ENCRYPTION_KEYS": DEV_ENCRYPTION_KEY}, "development key"),
        ({"INTERNAL_SERVICE_TOKEN": f"{DEV_SECRET_MARKER}-token"}, "INTERNAL_SERVICE_TOKEN"),
        ({"TRUSTED_HOSTS": ["*"]}, "TRUSTED_HOSTS"),
        ({"DEBUG": True}, "DEBUG"),
    ],
)
def test_production_refuses_unsafe_settings(override: dict[str, object], complaint: str) -> None:
    with pytest.raises(ValueError, match=complaint):
        _production(**override).validate_security()


def test_an_invalid_encryption_key_is_rejected_in_every_environment() -> None:
    with pytest.raises(ValueError, match="Fernet"):
        Settings(ENVIRONMENT="local", TEST_CASE_ENCRYPTION_KEYS="not-a-key").validate_security()
    with pytest.raises(ValueError, match="at least one"):
        Settings(ENVIRONMENT="local", TEST_CASE_ENCRYPTION_KEYS=" , ").validate_security()


def test_the_development_key_is_a_valid_fernet_key() -> None:
    assert len(base64.urlsafe_b64decode(DEV_ENCRYPTION_KEY)) == 32
    SecretCipher([DEV_ENCRYPTION_KEY]).encrypt("x")
