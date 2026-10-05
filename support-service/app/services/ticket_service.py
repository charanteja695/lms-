"""The ticket lifecycle (docs/PRODUCT.md §5.5): open → assigned → waiting_on_student → resolved → closed, with SLA timers,
reopening within a window, auto-close, and a CSAT rating afterwards.

Every change to a ticket takes a row lock on it first (``_lock``), so two agents replying at once get consecutive message
numbers, two claims cannot both win, and the SLA clock cannot be paused and resumed twice. Every change writes an audit
event; the ones other services care about are also emitted through the outbox.
"""

from datetime import datetime, timedelta
from typing import Any

from lms_common.pagination import paginate
from sqlalchemy import ColumnElement, and_, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import (
    ACTIVE_STATUSES,
    QUEUE_FOR_CATEGORY,
    AuthorRole,
    Category,
    MessageKind,
    Priority,
    Queue,
    Source,
    TicketStatus,
)
from app.models.config import CannedReply, SlaPolicy, UserRef
from app.models.ticket import Ticket, TicketEvent, TicketMessage
from app.permissions import policy
from app.permissions.roles import Role
from app.services.outbox import write_event
from app.sla import Targets, due_at, is_breached, minutes_between, paused_total, targets_for

_DEFAULT_PRIORITY = {Category.INTEGRITY: Priority.HIGH}


def _iso(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class TicketService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ plumbing
    async def _targets(self, queue: str, priority: str) -> Targets:
        rows = (await self.db.execute(select(SlaPolicy).where(SlaPolicy.queue == queue, SlaPolicy.priority == priority))).scalars().all()
        overrides = {(r.queue, r.priority): Targets(r.first_response_minutes, r.resolution_minutes) for r in rows}
        return targets_for(queue, priority, overrides)

    async def _apply_sla(self, ticket: Ticket) -> None:
        targets = await self._targets(ticket.queue, ticket.priority)
        anchor = ticket.sla_anchor_at or ticket.created_at
        if ticket.first_response_at is None:
            ticket.first_response_due_at = due_at(anchor, targets.first_response_minutes, ticket.sla_paused_seconds)
        ticket.resolution_due_at = due_at(anchor, targets.resolution_minutes, ticket.sla_paused_seconds)

    async def _lock(self, ticket: Ticket) -> Ticket:
        return (await self.db.execute(select(Ticket).where(Ticket.id == ticket.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    def _audit(self, ticket: Ticket, event_type: str, actor: int | None, **detail: Any) -> None:
        self.db.add(TicketEvent(ticket_id=ticket.id, event_type=event_type, actor_user_id=actor, detail=detail or None))
        ticket.last_activity_at = utcnow()

    def _emit(self, event_type: str, ticket: Ticket, **extra: Any) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="ticket", aggregate_id=ticket.id,
            payload={
                "ticket_id": str(ticket.public_id), "requester_user_id": str(ticket.requester_user_id),
                "organization_id": str(ticket.organization_id) if ticket.organization_id else None, "category": ticket.category, "queue": ticket.queue,
                "priority": ticket.priority, "status": ticket.status, "assignee_user_id": str(ticket.assignee_user_id) if ticket.assignee_user_id else None,
                "occurred_at": _iso(utcnow()), **extra,
            },
        )

    async def _add_message(self, ticket: Ticket, *, author_user_id: int | None, role: AuthorRole, kind: MessageKind, body: str, canned_id: int | None = None) -> TicketMessage:
        last = (await self.db.execute(select(func.max(TicketMessage.seq)).where(TicketMessage.ticket_id == ticket.id))).scalar_one()
        message = TicketMessage(public_id=new_public_id(), ticket_id=ticket.id, seq=(last or 0) + 1, author_user_id=author_user_id, author_role=role, kind=kind, body=body, canned_reply_id=canned_id)
        self.db.add(message)
        ticket.last_activity_at = utcnow()
        await self.db.flush()
        return message

    @staticmethod
    def _resume_clock(ticket: Ticket, now: datetime) -> None:
        """End a pause: the time spent waiting is added to the paused total and pushes every open due time out by that much."""
        total = paused_total(ticket.sla_paused_seconds, ticket.sla_paused_at, now)
        delta = timedelta(seconds=total - ticket.sla_paused_seconds)
        ticket.sla_paused_seconds, ticket.sla_paused_at = total, None
        if ticket.first_response_at is None and ticket.first_response_due_at is not None:
            ticket.first_response_due_at += delta
        if ticket.resolution_due_at is not None:
            ticket.resolution_due_at += delta

    def _set_status(self, ticket: Ticket, new: TicketStatus, actor: int | None) -> None:
        old = TicketStatus(ticket.status)
        if old == new:
            return
        now = utcnow()
        if old == TicketStatus.WAITING_ON_STUDENT:  # the student answered (or an agent moved on): the clock runs again
            self._resume_clock(ticket, now)
        if new == TicketStatus.WAITING_ON_STUDENT:
            ticket.sla_paused_at = now
        ticket.status = new
        self._audit(ticket, "status_changed", actor, **{"from": old.value, "to": new.value})
        self._emit("ticket.status_changed", ticket, previous_status=old.value)

    # ------------------------------------------------------------------ create / read
    async def create(
        self, *, requester_user_id: int, organization_id: int | None, subject: str, description: str, category: Category, source: Source,
        source_ref: str | None = None, course_id: int | None = None, idempotency_key: str | None = None, reason: str | None = None,
    ) -> tuple[Ticket, bool]:
        """Open a ticket. With an ``idempotency_key`` a retry returns the ticket it already opened. Returns ``(ticket, created)``."""
        if idempotency_key:
            existing = (await self.db.execute(select(Ticket).where(Ticket.idempotency_key == idempotency_key))).scalar_one_or_none()
            if existing is not None:
                return existing, False
        now = utcnow()
        priority = _DEFAULT_PRIORITY.get(category, Priority.NORMAL)
        ticket = Ticket(
            public_id=new_public_id(), organization_id=organization_id, requester_user_id=requester_user_id, subject=subject, category=category,
            queue=QUEUE_FOR_CATEGORY[category], priority=priority, status=TicketStatus.OPEN, source=source, source_ref=source_ref, course_id=course_id,
            idempotency_key=idempotency_key, sla_anchor_at=now, created_at=now, last_activity_at=now, sla_paused_seconds=0, reopened_count=0,
            first_response_breached=False, resolution_breached=False,
        )
        try:
            async with self.db.begin_nested():  # a retry that races the first request loses on the unique key, and gets the winner's ticket
                self.db.add(ticket)
                await self._apply_sla(ticket)
                await self.db.flush()
        except IntegrityError:
            if not idempotency_key:
                raise
            winner = (await self.db.execute(select(Ticket).where(Ticket.idempotency_key == idempotency_key))).scalar_one()
            return winner, False
        await self._add_message(ticket, author_user_id=requester_user_id, role=AuthorRole.REQUESTER, kind=MessageKind.PUBLIC, body=description)
        self._audit(ticket, "created", requester_user_id, source=str(source), **({"reason": reason} if reason else {}))
        self._emit("ticket.created", ticket, source=str(source), course_id=str(course_id) if course_id else None, first_response_due_at=_iso(ticket.first_response_due_at))
        return ticket, True

    async def get(self, public_id: int) -> Ticket:
        ticket = (await self.db.execute(select(Ticket).where(Ticket.public_id == public_id))).scalar_one_or_none()
        if ticket is None:
            raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
        return ticket

    async def messages(self, ticket: Ticket, *, include_internal: bool) -> list[TicketMessage]:
        stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.seq)
        if not include_internal:
            stmt = stmt.where(TicketMessage.kind != MessageKind.INTERNAL)
        return list((await self.db.execute(stmt)).scalars())

    async def events(self, ticket: Ticket) -> list[TicketEvent]:
        return list((await self.db.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id).order_by(TicketEvent.created_at, TicketEvent.id))).scalars())

    # ------------------------------------------------------------------ the requester
    async def reply_as_requester(self, ticket: Ticket, user_id: int, body: str) -> tuple[Ticket, TicketMessage]:
        ticket = await self._lock(ticket)
        now = utcnow()
        if ticket.status == TicketStatus.CLOSED:
            raise ConflictError("This ticket is closed. Please open a new one.", code="TICKET_CLOSED")
        if ticket.status == TicketStatus.RESOLVED:
            if ticket.resolved_at is not None and now > ticket.resolved_at + timedelta(days=self.settings.REOPEN_WINDOW_DAYS):
                raise ConflictError("This ticket was resolved too long ago to reopen. Please open a new one.", code="REOPEN_WINDOW_PASSED")
            await self._reopen(ticket, user_id)
        message = await self._add_message(ticket, author_user_id=user_id, role=AuthorRole.REQUESTER, kind=MessageKind.PUBLIC, body=body)
        if ticket.status == TicketStatus.WAITING_ON_STUDENT:
            self._set_status(ticket, TicketStatus.ASSIGNED if ticket.assignee_user_id else TicketStatus.OPEN, user_id)
        self._audit(ticket, "requester_replied", user_id)
        await self.db.commit()
        return ticket, message

    async def _reopen(self, ticket: Ticket, actor: int | None) -> None:
        now = utcnow()
        old = ticket.status
        ticket.status = TicketStatus.ASSIGNED if ticket.assignee_user_id else TicketStatus.OPEN
        ticket.resolved_at = None
        ticket.reopened_count += 1
        ticket.sla_anchor_at, ticket.sla_paused_seconds, ticket.sla_paused_at = now, 0, None
        ticket.resolution_breached = False
        await self._apply_sla(ticket)
        self._audit(ticket, "reopened", actor, count=ticket.reopened_count)
        self._emit("ticket.status_changed", ticket, previous_status=old, reopened=True)

    async def close_as_requester(self, ticket: Ticket, user_id: int) -> Ticket:
        ticket = await self._lock(ticket)
        if ticket.status == TicketStatus.CLOSED:
            return ticket
        self._close(ticket, user_id, reason="requester")
        await self.db.commit()
        return ticket

    def _close(self, ticket: Ticket, actor: int | None, *, reason: str) -> None:
        old = ticket.status
        if old == TicketStatus.WAITING_ON_STUDENT:
            self._resume_clock(ticket, utcnow())
        ticket.status, ticket.closed_at = TicketStatus.CLOSED, utcnow()
        if ticket.csat_requested_at is None:
            ticket.csat_requested_at = ticket.closed_at
        self._audit(ticket, "closed", actor, reason=reason, **{"from": old})
        self._emit("ticket.status_changed", ticket, previous_status=old, reason=reason)

    async def submit_csat(self, ticket: Ticket, user_id: int, rating: int, comment: str | None) -> Ticket:
        ticket = await self._lock(ticket)
        if ticket.status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            raise ConflictError("You can rate a ticket once it is resolved.", code="NOT_RESOLVED")
        if ticket.csat_rating is not None:
            raise ConflictError("You have already rated this ticket.", code="CSAT_ALREADY_SUBMITTED")
        ticket.csat_rating, ticket.csat_comment, ticket.csat_submitted_at = rating, comment, utcnow()
        self._audit(ticket, "csat_submitted", user_id, rating=rating)
        self._emit("ticket.csat_submitted", ticket, rating=rating)
        await self.db.commit()
        return ticket

    # ------------------------------------------------------------------ agents
    def _require_handler(self, auth: AccessTokenClaims, ticket: Ticket) -> None:
        if not policy.can_handle(auth, ticket):
            raise PermissionDeniedError("You do not handle this ticket's queue.", code="NOT_YOUR_QUEUE")

    async def reply_as_agent(
        self, ticket: Ticket, auth: AccessTokenClaims, *, body: str, internal: bool, then: str | None, canned_reply_id: int | None = None
    ) -> tuple[Ticket, TicketMessage]:
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.status == TicketStatus.CLOSED:
            raise ConflictError("This ticket is closed.", code="TICKET_CLOSED")
        now = utcnow()
        message = await self._add_message(
            ticket, author_user_id=auth.user_id, role=AuthorRole.AGENT, kind=MessageKind.INTERNAL if internal else MessageKind.PUBLIC, body=body, canned_id=canned_reply_id
        )
        if internal:
            self._audit(ticket, "internal_note", auth.user_id)
            await self.db.commit()
            return ticket, message
        if ticket.assignee_user_id is None:  # answering a ticket is taking it
            ticket.assignee_user_id, ticket.assigned_at = auth.user_id, now
            if ticket.status == TicketStatus.OPEN:
                self._set_status(ticket, TicketStatus.ASSIGNED, auth.user_id)
            self._audit(ticket, "assigned", auth.user_id, assignee=str(auth.user_id))
            self._emit("ticket.assigned", ticket)
        if ticket.first_response_at is None:
            ticket.first_response_at = now
            self._audit(ticket, "first_response", auth.user_id, minutes=minutes_between(ticket.sla_anchor_at or ticket.created_at, now))
        self._audit(ticket, "agent_replied", auth.user_id)
        self._emit("ticket.replied", ticket, message_id=str(message.public_id))
        if then == "waiting_on_student" and ticket.status in ACTIVE_STATUSES:
            self._set_status(ticket, TicketStatus.WAITING_ON_STUDENT, auth.user_id)
        elif then == "resolved" and ticket.status in ACTIVE_STATUSES:
            self._resolve(ticket, auth.user_id)
        await self.db.commit()
        return ticket, message

    def _resolve(self, ticket: Ticket, actor: int | None) -> None:
        self._set_status(ticket, TicketStatus.RESOLVED, actor)
        ticket.resolved_at = utcnow()
        ticket.csat_requested_at = ticket.resolved_at  # the student is asked how it went
        self._emit("ticket.csat_requested", ticket)

    async def resolve(self, ticket: Ticket, auth: AccessTokenClaims) -> Ticket:
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.status not in ACTIVE_STATUSES:
            raise ConflictError(f"A {ticket.status} ticket cannot be resolved.", code="NOT_ACTIVE")
        self._resolve(ticket, auth.user_id)
        await self.db.commit()
        return ticket

    async def reopen(self, ticket: Ticket, auth: AccessTokenClaims) -> Ticket:
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.status != TicketStatus.RESOLVED:
            raise ConflictError("Only a resolved ticket can be reopened.", code="NOT_RESOLVED")
        await self._reopen(ticket, auth.user_id)
        await self.db.commit()
        return ticket

    async def close(self, ticket: Ticket, auth: AccessTokenClaims) -> Ticket:
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.status != TicketStatus.CLOSED:
            self._close(ticket, auth.user_id, reason="agent")
        await self.db.commit()
        return ticket

    async def claim(self, ticket: Ticket, auth: AccessTokenClaims) -> Ticket:
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.status not in ACTIVE_STATUSES:
            raise ConflictError("Only an open ticket can be claimed.", code="NOT_ACTIVE")
        if ticket.assignee_user_id not in (None, auth.user_id) and not policy.is_manager(auth):
            raise ConflictError("Someone else already has this ticket.", code="ALREADY_ASSIGNED")
        self._assign(ticket, auth.user_id, auth.user_id)
        await self.db.commit()
        return ticket

    def _assign(self, ticket: Ticket, assignee: int, actor: int) -> None:
        if ticket.assignee_user_id == assignee:
            return
        ticket.assignee_user_id, ticket.assigned_at = assignee, utcnow()
        if ticket.status == TicketStatus.OPEN:
            self._set_status(ticket, TicketStatus.ASSIGNED, actor)
        self._audit(ticket, "assigned", actor, assignee=str(assignee))
        self._emit("ticket.assigned", ticket)

    @staticmethod
    def _eligible(ticket: Ticket) -> ColumnElement[bool]:
        """Who may hold a ticket of this queue: its institution's staff/head for batch_staff, platform admins otherwise."""
        if ticket.queue == Queue.BATCH_STAFF:
            return and_(UserRef.role.in_((Role.STAFF, Role.INSTITUTION_HEAD)), UserRef.organization_id == ticket.organization_id)
        return UserRef.role.in_((Role.ADMIN, Role.SUPER_ADMIN))

    async def assignees(self, ticket: Ticket, auth: AccessTokenClaims) -> list[UserRef]:
        """The people this ticket may be assigned to — the same rule ``assign`` enforces."""
        if not policy.can_assign_others(auth, ticket):
            raise PermissionDeniedError("You may not assign this ticket to someone else.", code="CANNOT_ASSIGN")
        stmt = select(UserRef).where(UserRef.active.is_(True), self._eligible(ticket)).order_by(UserRef.first_name, UserRef.last_name).limit(200)
        return list((await self.db.execute(stmt)).scalars())

    async def assign(self, ticket: Ticket, auth: AccessTokenClaims, assignee_user_id: int) -> Ticket:
        if not policy.can_assign_others(auth, ticket):
            raise PermissionDeniedError("You may not assign this ticket to someone else.", code="CANNOT_ASSIGN")
        eligible = (
            await self.db.execute(select(UserRef.user_id).where(UserRef.user_id == assignee_user_id, UserRef.active.is_(True), self._eligible(ticket)))
        ).scalar_one_or_none() is not None
        if not eligible:
            raise ValidationFailedError("That person cannot handle this ticket's queue.", code="ASSIGNEE_NOT_ELIGIBLE")
        ticket = await self._lock(ticket)
        if ticket.status not in ACTIVE_STATUSES:
            raise ConflictError("Only an open ticket can be assigned.", code="NOT_ACTIVE")
        self._assign(ticket, assignee_user_id, auth.user_id)
        await self.db.commit()
        return ticket

    async def release(self, ticket: Ticket, auth: AccessTokenClaims) -> Ticket:
        """Hand a ticket back to its queue."""
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.assignee_user_id not in (auth.user_id, None) and not policy.is_manager(auth):
            raise PermissionDeniedError("Only the assignee or a manager can release this ticket.", code="NOT_ASSIGNEE")
        if ticket.status in ACTIVE_STATUSES:
            ticket.assignee_user_id = ticket.assigned_at = None
            if ticket.status == TicketStatus.ASSIGNED:
                self._set_status(ticket, TicketStatus.OPEN, auth.user_id)
            self._audit(ticket, "released", auth.user_id)
        await self.db.commit()
        return ticket

    async def update(self, ticket: Ticket, auth: AccessTokenClaims, *, priority: Priority | None, category: Category | None) -> Ticket:
        self._require_handler(auth, ticket)
        ticket = await self._lock(ticket)
        if ticket.status == TicketStatus.CLOSED:
            raise ConflictError("This ticket is closed.", code="TICKET_CLOSED")
        if priority is not None and priority != ticket.priority:
            self._audit(ticket, "priority_changed", auth.user_id, **{"from": ticket.priority, "to": priority.value})
            ticket.priority = priority
        if category is not None and category != ticket.category:
            new_queue = QUEUE_FOR_CATEGORY[category]
            self._audit(ticket, "recategorized", auth.user_id, **{"from": ticket.category, "to": category.value, "queue": new_queue.value})
            ticket.category = category
            if new_queue != ticket.queue:  # re-routed: it goes back to the new queue unassigned
                ticket.queue, ticket.assignee_user_id, ticket.assigned_at = new_queue, None, None
                if ticket.status == TicketStatus.ASSIGNED:
                    self._set_status(ticket, TicketStatus.OPEN, auth.user_id)
        await self._apply_sla(ticket)
        await self.db.commit()
        return ticket

    # ------------------------------------------------------------------ canned replies
    async def render_canned(self, reply: CannedReply, ticket: Ticket) -> str:
        person = await self.db.get(UserRef, ticket.requester_user_id)
        return reply.body.replace("{{student_first_name}}", (person.first_name if person and person.first_name else "there")).replace("{{ticket_subject}}", ticket.subject)

    # ------------------------------------------------------------------ lists and reports
    @staticmethod
    def visible_to(auth: AccessTokenClaims) -> ColumnElement[bool]:
        """The tickets an agent may see: everything for a manager, else the queues they handle."""
        if policy.is_manager(auth):
            return Ticket.id.is_not(None)
        clauses: list[ColumnElement[bool]] = []
        if policy.is_exam_team(auth):
            clauses.append(Ticket.queue == Queue.EXAM_TEAM)
        if policy.is_institution_staff(auth):
            clauses.append(and_(Ticket.queue == Queue.BATCH_STAFF, Ticket.organization_id == auth.organization_id))
        return or_(*clauses) if clauses else false()

    async def list_mine(self, user_id: int, *, status: str | None, page: int, per_page: int) -> tuple[list[Ticket], int, bool]:
        stmt = select(Ticket).where(Ticket.requester_user_id == user_id).order_by(Ticket.created_at.desc(), Ticket.id)
        if status:
            stmt = stmt.where(Ticket.status == status)
        return await paginate(self.db, stmt, page, per_page)

    async def list_queue(
        self, auth: AccessTokenClaims, *, status: str | None, queue: str | None, priority: str | None, category: str | None, assignee: str | None,
        breached: bool | None, q: str | None, course_id: int | None, requester: int | None, sort: str, page: int, per_page: int,
    ) -> tuple[list[Ticket], int, bool]:
        stmt = select(Ticket).where(self.visible_to(auth))
        if status:
            stmt = stmt.where(Ticket.status == status)
        else:
            stmt = stmt.where(Ticket.status.in_([s.value for s in ACTIVE_STATUSES]))
        for column, value in ((Ticket.queue, queue), (Ticket.priority, priority), (Ticket.category, category), (Ticket.course_id, course_id), (Ticket.requester_user_id, requester)):
            if value is not None:
                stmt = stmt.where(column == value)
        if assignee == "me":
            stmt = stmt.where(Ticket.assignee_user_id == auth.user_id)
        elif assignee == "unassigned":
            stmt = stmt.where(Ticket.assignee_user_id.is_(None))
        elif assignee:
            stmt = stmt.where(Ticket.assignee_user_id == int(assignee))
        if breached is True:
            stmt = stmt.where(or_(Ticket.first_response_breached.is_(True), Ticket.resolution_breached.is_(True)))
        elif breached is False:
            stmt = stmt.where(Ticket.first_response_breached.is_(False), Ticket.resolution_breached.is_(False))
        if q:
            stmt = stmt.where(Ticket.subject.ilike(f"%{q.replace('%', '').replace('_', ' ')}%"))
        order = {"due": (Ticket.first_response_due_at.asc().nullslast(), Ticket.created_at), "activity": (Ticket.last_activity_at.desc(),)}.get(sort, (Ticket.created_at.desc(),))
        return await paginate(self.db, stmt.order_by(*order, Ticket.id), page, per_page)

    async def summary(self, auth: AccessTokenClaims) -> dict[str, Any]:
        rows = (await self.db.execute(select(Ticket).where(self.visible_to(auth), Ticket.status.in_([s.value for s in ACTIVE_STATUSES])).limit(20_000))).scalars().all()
        now = utcnow()
        queues: dict[str, dict[str, Any]] = {}
        for t in rows:
            entry = queues.setdefault(t.queue, {"queue": t.queue, "open": 0, "assigned": 0, "waiting_on_student": 0, "unassigned": 0, "breached": 0, "oldest_unanswered_minutes": None})
            entry[t.status] += 1
            entry["unassigned"] += int(t.assignee_user_id is None)
            entry["breached"] += int(t.first_response_breached or t.resolution_breached)
            if t.first_response_at is None and t.status != TicketStatus.WAITING_ON_STUDENT:
                age = minutes_between(t.created_at, now) or 0.0
                entry["oldest_unanswered_minutes"] = max(entry["oldest_unanswered_minutes"] or 0.0, age)
        return {"queues": sorted(queues.values(), key=lambda e: e["queue"])}

    async def sla_report(self, auth: AccessTokenClaims, *, start: datetime, end: datetime) -> dict[str, Any]:
        rows = (await self.db.execute(select(Ticket).where(self.visible_to(auth), Ticket.created_at >= start, Ticket.created_at < end).limit(20_000))).scalars().all()
        total = len(rows)
        first = [minutes_between(t.created_at, t.first_response_at) for t in rows if t.first_response_at]
        resolved = [minutes_between(t.created_at, t.resolved_at or t.closed_at) for t in rows if t.resolved_at or t.closed_at]
        rated = [t.csat_rating for t in rows if t.csat_rating is not None]

        def avg(values: list[float | None]) -> float | None:
            present = [v for v in values if v is not None]
            return round(sum(present) / len(present), 1) if present else None

        return {
            "tickets": total, "resolved": len(resolved), "first_response_breached": sum(t.first_response_breached for t in rows),
            "resolution_breached": sum(t.resolution_breached for t in rows),
            "first_response_compliance": round(1 - sum(t.first_response_breached for t in rows) / total, 4) if total else None,
            "resolution_compliance": round(1 - sum(t.resolution_breached for t in rows) / total, 4) if total else None,
            "avg_first_response_minutes": avg(first), "avg_resolution_minutes": avg(resolved), "csat_responses": len(rated),
            "csat_average": round(sum(rated) / len(rated), 2) if rated else None, "reopened": sum(1 for t in rows if t.reopened_count),
            "truncated": total >= 20_000,
        }


async def sweep_sla(db: AsyncSession, settings: Settings) -> int:
    """Flag tickets that have passed a due time (once each) and close resolved ones nobody answered. Run by the worker."""
    now = utcnow()
    service = TicketService(db, settings)
    flagged = 0
    active = [s.value for s in ACTIVE_STATUSES]
    first = (
        await db.execute(
            select(Ticket).where(
                Ticket.status.in_(active), Ticket.first_response_at.is_(None), Ticket.first_response_breached.is_(False), Ticket.sla_paused_at.is_(None), Ticket.first_response_due_at < now
            ).limit(settings.SLA_SWEEP_BATCH).with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for ticket in first:
        if is_breached(now, ticket.first_response_due_at, paused=ticket.sla_paused_at is not None):
            ticket.first_response_breached = True
            service._audit(ticket, "sla_breached", None, kind="first_response")
            service._emit("ticket.sla_breached", ticket, kind="first_response")
            flagged += 1
    resolution = (
        await db.execute(
            select(Ticket).where(Ticket.status.in_(active), Ticket.resolution_breached.is_(False), Ticket.sla_paused_at.is_(None), Ticket.resolution_due_at < now).limit(settings.SLA_SWEEP_BATCH).with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for ticket in resolution:
        ticket.resolution_breached = True
        service._audit(ticket, "sla_breached", None, kind="resolution")
        service._emit("ticket.sla_breached", ticket, kind="resolution")
        flagged += 1
    stale = (
        await db.execute(
            select(Ticket).where(Ticket.status == TicketStatus.RESOLVED, Ticket.resolved_at < now - timedelta(days=settings.AUTO_CLOSE_AFTER_DAYS)).limit(settings.SLA_SWEEP_BATCH).with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for ticket in stale:
        service._close(ticket, None, reason="auto_close")
        flagged += 1
    await db.commit()
    return flagged
