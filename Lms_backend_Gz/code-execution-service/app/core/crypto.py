"""Encryption of test cases and SQL setup scripts at rest (docs/PRODUCT.md §5.2: "stored encrypted and never
sent to the client"). Fernet (AES-128-CBC + HMAC-SHA256); the database alone reveals nothing about a hidden test.

Several keys may be configured, newest first: everything is encrypted with the first, and any of them can
decrypt, so a key is rotated by prepending a new one, then running ``python -m app.cli rotate-keys``.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import Settings
from app.core.exceptions import AppError


class DecryptionError(AppError):
    status_code = 500
    code = "DECRYPTION_FAILED"
    message = "Stored test data could not be decrypted. Check TEST_CASE_ENCRYPTION_KEYS."


class SecretCipher:
    def __init__(self, keys: list[str]) -> None:
        self._fernet = MultiFernet([Fernet(key) for key in keys])

    @classmethod
    def from_settings(cls, settings: Settings) -> "SecretCipher":
        return cls(settings.encryption_keys)

    def encrypt(self, text: str) -> str:
        return self._fernet.encrypt(text.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise DecryptionError() from exc

    def rotate(self, token: str) -> str:
        """Re-encrypt under the newest key (a no-op in effect if it already is)."""
        try:
            return self._fernet.rotate(token.encode()).decode()
        except InvalidToken as exc:
            raise DecryptionError() from exc
