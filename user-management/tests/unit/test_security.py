import jwt
import pytest

from app.core.config import get_settings
from app.core.ids import new_public_id, parse_public_id
from app.core.password_policy import password_problems
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.types import uuid7


async def test_password_hash_roundtrip() -> None:
    hashed = await hash_password("Str0ng!Passphrase#1")
    assert hashed.startswith("$argon2id$")
    assert (await verify_password(hashed, "Str0ng!Passphrase#1"))[0]
    assert not (await verify_password(hashed, "wrong"))[0]
    assert not (await verify_password("not-a-hash", "anything"))[0]


def test_token_hash_is_keyed_and_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("abc")) == 64


def _token() -> str:
    token, _ = create_access_token(
        user_id=new_public_id(), session_id=new_public_id(), role="admin", organization_id=None, token_version=3
    )
    return token


def test_access_token_roundtrip() -> None:
    claims = decode_access_token(_token())
    assert claims.role == "admin"
    assert claims.token_version == 3
    assert claims.organization_id is None


def test_tampered_or_foreign_tokens_are_rejected() -> None:
    settings = get_settings()
    token = _token()
    with pytest.raises(TokenError):
        decode_access_token(token[:-2] + ("aa" if token[-2:] != "aa" else "bb"))

    payload = jwt.decode(token, options={"verify_signature": False})
    with pytest.raises(TokenError):
        decode_access_token(jwt.encode(payload, "another-secret-key-that-is-long-enough", algorithm="HS256"))
    with pytest.raises(TokenError):
        decode_access_token(jwt.encode({**payload, "type": "refresh"}, settings.JWT_SECRET_KEY.get_secret_value()))
    with pytest.raises(TokenError):
        decode_access_token(jwt.encode({**payload, "aud": "other"}, settings.JWT_SECRET_KEY.get_secret_value()))
    unsigned = jwt.encode(payload, None, algorithm="none")  # type: ignore[arg-type]
    with pytest.raises(TokenError):
        decode_access_token(unsigned)


def test_password_policy() -> None:
    assert password_problems("Str0ng!Passphrase#1", min_length=12) == []
    assert password_problems("short", min_length=12)
    assert password_problems("alllowercase123!", min_length=12)
    assert password_problems("John.Smith#2024", min_length=12, username="john.smith")


def test_uuid7_is_time_ordered() -> None:
    ids = [uuid7() for _ in range(50)]
    assert all(u.version == 7 for u in ids)
    assert [u.bytes[:6] for u in ids] == sorted(u.bytes[:6] for u in ids)


def test_public_ids_are_numeric_strings_and_time_ordered() -> None:
    ids = [new_public_id() for _ in range(20)]
    assert all(parse_public_id(str(i)) == i for i in ids)
    timestamps = [i >> 22 for i in ids]  # the millisecond part; the low 22 bits are random
    assert timestamps == sorted(timestamps)
    for bad in ("abc", "0123456789", "-1", "1" * 25, "12345", 12345678901, None):
        assert parse_public_id(bad) is None
