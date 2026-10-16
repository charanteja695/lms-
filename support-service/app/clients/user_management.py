"""user-management's internal API: which people hold a permission right now (role defaults plus per-person grants and
removals), so a ticket is only assigned to someone who may handle it. Called with the internal token."""

import httpx

from app.core.config import Settings


class UserManagementUnavailable(Exception):
    """A timeout, a 5xx, or no answer at all."""


class UserManagementClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    async def holders(self, permissions: tuple[str, ...], user_ids: list[int]) -> set[int]:
        """Of ``user_ids``, those holding any of ``permissions``."""
        if not user_ids:
            return set()
        headers = {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}
        found: set[int] = set()
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.USER_MANAGEMENT_URL.rstrip("/"), timeout=self.settings.USER_MANAGEMENT_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                for permission in permissions:
                    response = await client.post(
                        "/api/v1/internal/permission-holders", json={"permission": permission, "user_ids": [str(u) for u in user_ids]}, headers=headers
                    )
                    if response.status_code >= 400:
                        raise UserManagementUnavailable(f"user-management answered {response.status_code}")
                    found.update(int(u) for u in response.json()["user_ids"])
        except httpx.HTTPError as exc:
            raise UserManagementUnavailable(f"user-management unreachable: {exc.__class__.__name__}") from exc
        return found
