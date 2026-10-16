"""Read the Redis keys user-management publishes so a verified token can still be rejected
within seconds of a suspend, delete, role change or sign-out (see user-management's
``app/core/access_state.py``, which writes these keys from ``access.*`` outbox events):

    {prefix}:session:{session_id}   exists                 -> that device was signed out
    {prefix}:user:{user_id}         minimum token version   -> reject if token.ver < value
    {prefix}:org:{organization_id}  unix seconds             -> reject if token.iat <= value
    {prefix}:role:{role}            unix seconds             -> reject if token.iat <= value (a role's
                                                                permissions changed: everyone in it refreshes)

Call :func:`is_token_revoked` after :class:`~lms_common.auth.JWKSVerifier` verifies the
signature, before trusting the claims for anything.
"""

from dataclasses import dataclass

from redis.asyncio import Redis

DEFAULT_KEY_PREFIX = "lms:access"


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    session_id: str
    user_id: str
    organization_id: str | None
    token_version: int
    issued_at: int
    role: str | None = None


def _session_key(prefix: str, session_id: str) -> str:
    return f"{prefix}:session:{session_id}"


def _user_key(prefix: str, user_id: str) -> str:
    return f"{prefix}:user:{user_id}"


def _organization_key(prefix: str, organization_id: str) -> str:
    return f"{prefix}:org:{organization_id}"


def _role_key(prefix: str, role: str) -> str:
    return f"{prefix}:role:{role}"


async def is_token_revoked(redis: Redis, token: TokenIdentity, *, key_prefix: str = DEFAULT_KEY_PREFIX) -> bool:
    """One pipelined round trip; sub-millisecond in practice."""
    keys = [_session_key(key_prefix, token.session_id), _user_key(key_prefix, token.user_id)]
    keys.append(_organization_key(key_prefix, token.organization_id) if token.organization_id else _organization_key(key_prefix, "-"))
    keys.append(_role_key(key_prefix, token.role) if token.role else _role_key(key_prefix, "-"))
    values = await redis.mget(keys)
    session_revoked, min_version = values[0], values[1]
    org_revoked_at = values[2] if token.organization_id else None
    role_changed_at = values[3] if token.role else None
    if session_revoked is not None:
        return True
    if min_version is not None and token.token_version < int(min_version):
        return True
    if role_changed_at is not None and token.issued_at <= int(role_changed_at):
        return True
    return org_revoked_at is not None and token.issued_at <= int(org_revoked_at)
