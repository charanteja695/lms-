"""Handing a student to a person (docs/PRODUCT.md §5.5 "Escalation").

The tutor never blocks on support-service: it records an ``Escalation`` (the durable job) in the same transaction as the
message that triggered it and tells the student immediately. A worker then writes the hand-off note, opens the ticket in
support-service (idempotently — the escalation's id is the key), and retries with backoff if support-service is down.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.clients.gateway import GatewayClient, GatewayError
from app.clients.support import SupportClient, SupportRejected, SupportUnavailable
from app.core.config import Settings
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import ConversationStatus, EscalationCategory, EscalationReason, EscalationStatus
from app.models.conversation import Conversation, Escalation
from app.models.refs import CourseVersionRef
from app.services.outbox import write_event

logger = logging.getLogger(__name__)

_OPEN = (EscalationStatus.PENDING, EscalationStatus.CREATED)


def transcript_of(conversation: Conversation, limit: int, *, per_message: int = 600) -> str:
    lines = []
    for message in conversation.messages[-limit:]:
        who = "Student" if message.role == "user" else "Tutor"
        lines.append(f"{who}: {message.content[:per_message]}")
    return "\n".join(lines)


def fallback_summary(conversation: Conversation, reason: str, category: str) -> str:
    """Used when the summary model is unavailable: the last thing the student said, plainly."""
    asked = next((m.content for m in reversed(conversation.messages) if m.role == "user"), "")
    return f"The student's last message: \"{asked[:400]}\". Handed over by the tutor ({reason.replace('_', ' ')}; {category})."


def _backoff_seconds(attempts: int) -> int:
    return int(min(30 * 2 ** max(attempts - 1, 0), 3600))


class EscalationService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def open(self, conversation: Conversation, *, reason: EscalationReason, category: EscalationCategory) -> tuple[Escalation, bool]:
        """Record a hand-off; adds to the caller's transaction. A conversation already handed over for this category keeps
        its one open escalation — asking again does not open a second ticket. Returns ``(escalation, created)``."""
        existing = (
            await self.db.execute(
                select(Escalation).where(Escalation.conversation_id == conversation.id, Escalation.category == category, Escalation.status.in_(_OPEN)).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False
        subject = f"Tutor hand-off: {conversation.title or 'a question'}"[:200]
        escalation = Escalation(
            public_id=new_public_id(), conversation_id=conversation.id, conversation_public_id=conversation.public_id, user_id=conversation.user_id, organization_id=conversation.organization_id,
            course_id=conversation.course_id, reason=reason, category=category, subject=subject, status=EscalationStatus.PENDING, next_attempt_at=utcnow(),
        )
        self.db.add(escalation)
        conversation.status = ConversationStatus.ESCALATED
        await self.db.flush()
        write_event(
            self.db, event_type="tutor.escalated", aggregate_type="escalation", aggregate_id=escalation.id,
            payload={
                "escalation_id": str(escalation.public_id), "conversation_id": str(conversation.public_id), "student_user_id": str(conversation.user_id),
                "organization_id": str(conversation.organization_id) if conversation.organization_id else None,
                "course_id": str(conversation.course_id) if conversation.course_id else None, "reason": reason.value, "category": category.value,
                "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        return escalation, True

    async def claim(self, limit: int) -> list[Any]:
        now = utcnow()
        due = and_(
            Escalation.status == EscalationStatus.PENDING,
            or_(Escalation.lease_until.is_(None), Escalation.lease_until < now),
            or_(Escalation.next_attempt_at.is_(None), Escalation.next_attempt_at <= now),
        )
        rows = (await self.db.execute(select(Escalation).where(due).order_by(Escalation.created_at).limit(limit).with_for_update(skip_locked=True))).scalars().all()
        for row in rows:
            row.lease_until, row.attempts = now + timedelta(seconds=self.settings.ESCALATION_LEASE_SECONDS), row.attempts + 1
        await self.db.commit()
        return [row.id for row in rows]

    async def retry(self, escalation: Escalation) -> Escalation:
        """A support manager re-queues a failed hand-off."""
        escalation.status, escalation.attempts, escalation.next_attempt_at, escalation.lease_until, escalation.last_error = EscalationStatus.PENDING, 0, utcnow(), None, None
        await self.db.commit()
        return escalation


async def deliver_due(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, gateway: GatewayClient, support: SupportClient) -> int:
    async with sessionmaker() as db:
        ids = await EscalationService(db, settings).claim(settings.ESCALATION_BATCH_SIZE)
    for escalation_id in ids:
        async with sessionmaker() as db:
            escalation = await db.get(Escalation, escalation_id)
            if escalation is None:
                continue
            conversation = (
                await db.execute(select(Conversation).where(Conversation.id == escalation.conversation_id).options(selectinload(Conversation.messages)))
            ).scalar_one()
            course_title = None
            if conversation.version_id:
                ref = await db.get(CourseVersionRef, conversation.version_id)
                course_title = ref.title if ref else None
            transcript = transcript_of(conversation, settings.SUMMARY_MESSAGES)
            summary = escalation.summary or fallback_summary(conversation, escalation.reason, escalation.category)
            need_summary = escalation.summary is None
            organization_id, user_id, public_conversation_id = conversation.organization_id, conversation.user_id, conversation.public_id
            snapshot = {
                "subject": escalation.subject, "category": escalation.category, "reason": escalation.reason, "course_id": escalation.course_id,
                "public_id": escalation.public_id,
            }
        if need_summary:  # a model-written note is better than the fallback, but never worth losing the hand-off over
            try:
                done = await gateway.complete(
                    organization_id=organization_id or settings.PLATFORM_ORGANIZATION_ID, user_id=user_id, prompt_key=settings.SUMMARY_PROMPT_KEY, variables={},
                    messages=[{"role": "user", "content": transcript}], idempotency_key=f"tutor-summary:{snapshot['public_id']}",
                )
                if done.status == "ok" and done.content.strip():
                    summary = done.content.strip()
            except GatewayError:
                logger.info("escalation summary model unavailable; using the plain summary")
        description = summary if not course_title else f"{summary}\n\nCourse: {course_title}"
        payload = {
            "organization_id": str(organization_id) if organization_id else None, "requester_user_id": str(user_id), "subject": snapshot["subject"],
            "description": description[:6000], "category": snapshot["category"], "source": "ai-tutor", "source_ref": str(public_conversation_id),
            "reason": snapshot["reason"], "course_id": str(snapshot["course_id"]) if snapshot["course_id"] else None,
        }
        error: str | None = None
        ticket_id: int | None = None
        fatal = False
        try:
            ticket_id = (await support.create_ticket(payload, idempotency_key=str(snapshot["public_id"]))).ticket_id
        except SupportRejected as exc:
            error, fatal = f"rejected: {exc}"[:500], True
        except SupportUnavailable as exc:
            error = str(exc)[:500]
        async with sessionmaker() as db:
            row = (await db.execute(select(Escalation).where(Escalation.id == escalation_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
            row.summary, row.lease_until = summary, None
            if ticket_id is not None:
                row.status, row.ticket_id, row.last_error, row.next_attempt_at = EscalationStatus.CREATED, ticket_id, None, None
            elif fatal or row.attempts >= settings.ESCALATION_MAX_ATTEMPTS:
                row.status, row.last_error = EscalationStatus.FAILED, error
            else:
                row.last_error, row.next_attempt_at = error, utcnow() + timedelta(seconds=_backoff_seconds(row.attempts))
            await db.commit()
    return len(ids)
