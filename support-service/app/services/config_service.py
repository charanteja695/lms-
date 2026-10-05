"""Canned replies and SLA policy overrides."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DEFAULT_FIRST_RESPONSE_MINUTES, DEFAULT_RESOLUTION_MINUTES
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import CannedScope, Priority, Queue
from app.models.config import CannedReply, SlaPolicy
from app.permissions import policy


class ConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------- canned replies
    async def list_canned(self, auth: AccessTokenClaims, *, include_inactive: bool = False) -> list[CannedReply]:
        if policy.is_manager(auth):  # managers see every institution's replies too
            stmt = select(CannedReply).order_by(CannedReply.scope, CannedReply.title)
        else:
            clauses = [CannedReply.scope == CannedScope.PLATFORM]
            if auth.organization_id is not None:
                clauses.append((CannedReply.scope == CannedScope.ORGANIZATION) & (CannedReply.organization_id == auth.organization_id))
            stmt = select(CannedReply).where(or_(*clauses)).order_by(CannedReply.title)
        if not include_inactive:
            stmt = stmt.where(CannedReply.active.is_(True))
        return list((await self.db.execute(stmt)).scalars())

    async def get_canned(self, public_id: int) -> CannedReply:
        reply = (await self.db.execute(select(CannedReply).where(CannedReply.public_id == public_id))).scalar_one_or_none()
        if reply is None:
            raise NotFoundError("Canned reply not found.", code="CANNED_REPLY_NOT_FOUND")
        return reply

    @staticmethod
    def authorize_canned(auth: AccessTokenClaims, reply: CannedReply) -> None:
        if policy.is_manager(auth):
            return
        if reply.scope == CannedScope.ORGANIZATION and policy.is_institution_staff(auth) and reply.organization_id == auth.organization_id:
            return
        raise PermissionDeniedError("You may not change this canned reply.", code="CANNED_REPLY_FORBIDDEN")

    async def create_canned(self, auth: AccessTokenClaims, *, scope: CannedScope, title: str, body: str) -> CannedReply:
        if scope == CannedScope.PLATFORM and not policy.is_manager(auth):
            raise PermissionDeniedError("Only platform support can write platform-wide replies.", code="CANNED_REPLY_FORBIDDEN")
        if scope == CannedScope.ORGANIZATION and (auth.organization_id is None or not policy.is_institution_staff(auth)):
            raise PermissionDeniedError("Only institution staff can write an institution's replies.", code="CANNED_REPLY_FORBIDDEN")
        reply = CannedReply(
            public_id=new_public_id(), scope=scope, organization_id=auth.organization_id if scope == CannedScope.ORGANIZATION else None,
            title=title, body=body, active=True, created_by=auth.user_id,
        )
        self.db.add(reply)
        await self.db.commit()
        return reply

    async def update_canned(self, reply: CannedReply, *, title: str | None, body: str | None, active: bool | None) -> CannedReply:
        if title is not None:
            reply.title = title
        if body is not None:
            reply.body = body
        if active is not None:
            reply.active = active
        await self.db.commit()
        return reply

    # -------------------------------------------------------------- SLA policies
    async def policies(self) -> list[dict[str, object]]:
        rows = {(r.queue, r.priority): r for r in (await self.db.execute(select(SlaPolicy))).scalars()}
        out: list[dict[str, object]] = []
        for queue in Queue:
            for priority in Priority:
                row = rows.get((queue.value, priority.value))
                out.append({
                    "queue": queue.value, "priority": priority.value, "is_default": row is None,
                    "first_response_minutes": row.first_response_minutes if row else DEFAULT_FIRST_RESPONSE_MINUTES[priority.value],
                    "resolution_minutes": row.resolution_minutes if row else DEFAULT_RESOLUTION_MINUTES[priority.value],
                })
        return out

    async def upsert_policy(self, actor: int, *, queue: Queue, priority: Priority, first_response_minutes: int, resolution_minutes: int) -> None:
        if resolution_minutes < first_response_minutes:
            raise ConflictError("The resolution target cannot be shorter than the first-response target.", code="INVALID_SLA_TARGETS")
        row = (await self.db.execute(select(SlaPolicy).where(SlaPolicy.queue == queue, SlaPolicy.priority == priority))).scalar_one_or_none()
        if row is None:
            row = SlaPolicy(queue=queue, priority=priority, first_response_minutes=first_response_minutes, resolution_minutes=resolution_minutes)
            self.db.add(row)
        row.first_response_minutes, row.resolution_minutes, row.updated_by = first_response_minutes, resolution_minutes, actor
        await self.db.commit()

    async def reset_policy(self, queue: Queue, priority: Priority) -> None:
        row = (await self.db.execute(select(SlaPolicy).where(SlaPolicy.queue == queue, SlaPolicy.priority == priority))).scalar_one_or_none()
        if row is not None:
            await self.db.delete(row)
            await self.db.commit()
