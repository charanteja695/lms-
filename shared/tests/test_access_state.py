from fakeredis import FakeAsyncRedis
from lms_common.access_state import TokenIdentity, is_token_revoked

IDENTITY = TokenIdentity(session_id="1", user_id="2", organization_id="3", token_version=5, issued_at=1_000)


async def test_clear_token_is_not_revoked() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    assert await is_token_revoked(redis, IDENTITY) is False


async def test_session_key_revokes_that_session_only() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    await redis.set("lms:access:session:1", "1")
    assert await is_token_revoked(redis, IDENTITY) is True
    assert await is_token_revoked(redis, TokenIdentity("999", "2", "3", 5, 1_000)) is False


async def test_user_key_revokes_tokens_older_than_the_stored_version() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    await redis.set("lms:access:user:2", "6")
    assert await is_token_revoked(redis, IDENTITY) is True  # token.ver (5) < 6
    assert await is_token_revoked(redis, TokenIdentity("1", "2", "3", 6, 1_000)) is False


async def test_organization_key_revokes_tokens_issued_before_the_cutoff() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    await redis.set("lms:access:org:3", "2_000")
    assert await is_token_revoked(redis, IDENTITY) is True  # issued_at (1000) <= cutoff
    assert await is_token_revoked(redis, TokenIdentity("1", "2", "3", 5, 3_000)) is False


async def test_organization_without_id_ignores_the_org_key() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    await redis.set("lms:access:org:3", "999_999_999")
    no_org = TokenIdentity(session_id="1", user_id="2", organization_id=None, token_version=5, issued_at=1_000)
    assert await is_token_revoked(redis, no_org) is False
