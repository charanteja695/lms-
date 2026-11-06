"""Access state published for other microservices to read (the writer side).

Other services verify access tokens locally (JWKS) and never call this service per request. To stop a
suspended, deleted or signed-out user within seconds instead of at token expiry, revocations are projected
into Redis keys that every service checks (one pipelined round trip, sub-millisecond):

    lms:access:session:{session_id}        exists                 -> token.sid was signed out
    lms:access:user:{user_id}              minimum token version  -> reject if token.ver < value
    lms:access:org:{organization_id}       unix seconds           -> reject if token.iat <= value

Keys only need to outlive the longest access token, so they expire automatically.
The projection is fed by ``access.*`` outbox events (at-least-once, in commit order).

Only the issuer writes these keys, so this module stays local. The **reader** other services use
(``TokenIdentity`` and ``is_token_revoked``) lives in ``lms_common.access_state`` instead of here.
"""

from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings

SESSION_REVOKED = "access.session_revoked"
USER_REVOKED = "access.user_revoked"
ORGANIZATION_REVOKED = "access.organization_revoked"
# A role's permissions changed: tokens of that role issued before ``revoked_at`` must refresh (not sign out).
ROLE_REVOKED = "access.role_revoked"
ACCESS_EVENTS = frozenset({SESSION_REVOKED, USER_REVOKED, ORGANIZATION_REVOKED, ROLE_REVOKED})


def _ttl_seconds(settings: Settings) -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + settings.JWT_LEEWAY_SECONDS + 60


def session_key(settings: Settings, session_id: str) -> str:
    return f"{settings.ACCESS_STATE_KEY_PREFIX}:session:{session_id}"


def user_key(settings: Settings, user_id: str) -> str:
    return f"{settings.ACCESS_STATE_KEY_PREFIX}:user:{user_id}"


def role_key(settings: Settings, role: str) -> str:
    return f"{settings.ACCESS_STATE_KEY_PREFIX}:role:{role}"


def organization_key(settings: Settings, organization_id: str) -> str:
    return f"{settings.ACCESS_STATE_KEY_PREFIX}:org:{organization_id}"


async def apply_access_event(redis: Redis, settings: Settings, event_type: str, payload: dict[str, Any]) -> None:
    """Project one ``access.*`` event into Redis. Idempotent, so redelivery is harmless."""
    ttl = _ttl_seconds(settings)
    if event_type == SESSION_REVOKED:
        await redis.set(session_key(settings, payload["session_id"]), "1", ex=ttl)
    elif event_type == USER_REVOKED:
        await redis.set(user_key(settings, payload["user_id"]), int(payload["token_version"]), ex=ttl)
    elif event_type == ROLE_REVOKED:
        await redis.set(role_key(settings, payload["role"]), int(payload["revoked_at"]), ex=ttl)
    elif event_type == ORGANIZATION_REVOKED:
        await redis.set(organization_key(settings, payload["organization_id"]), int(payload["revoked_at"]), ex=ttl)
