"""One conversation turn, end to end (docs/PRODUCT.md §5.5).

The order is the design. Everything that must hold *whatever a model says* is decided here, in code, before a model is
asked anything, and the model is only told the outcome:

 1. the tutor is off inside a graded test                                     (refused, nothing saved)
 2. the student's message is saved                                            (so a failure later never loses it)
 3. a request for a person, or a matter of money / integrity / access         -> escalate, no model call
 4. the hint ladder for a practice problem                                    (the level is computed, never asked of the model)
 5. a published FAQ answer that matches closely                               -> answered as-is, no model call
 6. retrieval finds nothing relevant (low confidence)                         -> say so; a second miss escalates
 7. otherwise: the model answers from numbered sources / FAQ / read-only facts, and the answer cites them

No transaction is held open across a call to ai-gateway.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.gateway import (
    Completion,
    GatewayClient,
    GatewayDisabled,
    GatewayError,
    GatewayQuotaExceeded,
    GatewayUnavailable,
)
from app.core.config import Settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    TutorDisabledError,
    TutorUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import (
    ConversationMode,
    ConversationStatus,
    EscalationCategory,
    EscalationReason,
    MessageKind,
    MessageRole,
    RetrievalMethod,
)
from app.models.conversation import Conversation, Escalation, HintProgress, Message
from app.models.refs import AttemptRef, CertificateRef, CourseVersionRef, EnrollmentRef, ItemRef
from app.services.escalation_service import EscalationService
from app.services.retrieval_service import FaqHit, Passage, Retrieval, RetrievalService
from app.tutor import hints, prompts
from app.tutor.blocking import OpenAttempt, blocking_attempt
from app.tutor.context import SourceLine, build_user_message, clock, normalize_history
from app.tutor.triggers import asks_for_human, asks_for_solution, cited_numbers, lookups_wanted, sensitive_category

logger = logging.getLogger(__name__)

_GATEWAY_LIMIT = 19_500  # ai-gateway accepts 20,000 characters per message

REASON_TEXT = {
    EscalationReason.USER_REQUESTED: "Of course. I've asked a person to follow up on this conversation — you'll hear back through the platform. You can keep asking me things meanwhile.",
    EscalationReason.LOW_CONFIDENCE: "I still couldn't find this in your course material, so I've passed your question to a person who can help. You'll hear back through the platform.",
}
CATEGORY_TEXT = {
    EscalationCategory.BILLING: "Questions about payments, fees and refunds are handled by our team, not by me. I've opened a support request with this conversation attached.",
    EscalationCategory.INTEGRITY: "Test results and integrity decisions can only be discussed by the exam team, not by me. I've opened a support request with this conversation attached.",
    EscalationCategory.ACCESS: "Account and course-access problems need a person to look at them. I've opened a support request with this conversation attached.",
}
ALREADY_ESCALATED = "A person has already been asked to follow up on this conversation; they'll reply through the platform."
LOW_CONFIDENCE_TEXT = "I couldn't find that in your course material. Could you tell me which topic it's from, or say it another way? If it's still unclear I can ask your teacher."
BLOCKED_TEXT = "I can't help with that request."


@dataclass(frozen=True, slots=True)
class MessageContext:
    item_id: int | None = None
    code: str | None = None
    language: str | None = None
    hint_request: bool = False

    def as_json(self) -> dict[str, Any]:
        return {"item_id": str(self.item_id) if self.item_id else None, "language": self.language, "hint_request": self.hint_request, "has_code": bool(self.code)}


@dataclass(frozen=True, slots=True)
class Availability:
    enabled: bool
    reason: str | None = None
    attempt_id: int | None = None
    blocked_until: datetime | None = None


@dataclass(slots=True)
class Turn:
    user_message: Message
    assistant_message: Message
    escalation: Escalation | None = None


@dataclass(slots=True)
class _Plan:
    prompt_key: str
    variables: dict[str, str]
    messages: list[dict[str, str]]
    passages: list[Passage]
    faq: FaqHit | None
    method: RetrievalMethod
    top_score: float
    hint_level: int | None


@dataclass(slots=True)
class _Immediate:
    kind: MessageKind
    content: str
    escalation: Escalation | None = None
    citations: list[dict[str, Any]] | None = None
    confidence: float | None = None
    retrieval: RetrievalMethod | None = None
    hint_level: int | None = None


@dataclass(slots=True)
class _Decision:
    immediate: _Immediate | None = None
    plan: _Plan | None = None


def _map_gateway(exc: GatewayError) -> Exception:
    if isinstance(exc, GatewayQuotaExceeded):
        return QuotaExceededError()
    if isinstance(exc, GatewayDisabled):
        return TutorDisabledError("AI help is switched off for your institution right now.", code="TUTOR_DISABLED_FOR_ORGANIZATION")
    return TutorUnavailableError()


class TutorService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient, retrieval: RetrievalService) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.retrieval = retrieval

    # ------------------------------------------------------------------ conversations

    async def availability(self, user_id: int) -> Availability:
        attempt = await self._blocking_attempt(user_id)
        if attempt is None:
            return Availability(True)
        until = None if attempt.deadline_at is None else attempt.deadline_at
        return Availability(False, "GRADED_TEST_IN_PROGRESS", attempt.attempt_id, until)

    async def _blocking_attempt(self, user_id: int) -> OpenAttempt | None:
        rows = (await self.db.execute(select(AttemptRef).where(AttemptRef.user_id == user_id, AttemptRef.state == "in_progress"))).scalars().all()
        return blocking_attempt([OpenAttempt(r.attempt_id, r.test_kind, r.deadline_at) for r in rows], utcnow(), self.settings.TEST_BLOCK_GRACE_SECONDS)

    async def _enrolled_version(self, user_id: int, course_id: int) -> CourseVersionRef | None:
        row = (
            await self.db.execute(
                select(CourseVersionRef)
                .join(EnrollmentRef, EnrollmentRef.version_id == CourseVersionRef.version_id)
                .where(EnrollmentRef.student_user_id == user_id, EnrollmentRef.active.is_(True), CourseVersionRef.course_id == course_id, CourseVersionRef.retired.is_(False))
                .order_by(EnrollmentRef.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return row

    async def start(self, *, user_id: int, organization_id: int | None, mode: ConversationMode, course_id: int | None) -> Conversation:
        version_id = None
        if mode == ConversationMode.LEARNING and course_id is None:
            raise ValidationFailedError("A learning conversation needs a course.", code="COURSE_REQUIRED")
        if course_id is not None:
            version = await self._enrolled_version(user_id, course_id)
            if version is None:
                raise PermissionDeniedError("You are not enrolled in this course.", code="NOT_ENROLLED")
            version_id = version.version_id
        conversation = Conversation(public_id=new_public_id(), user_id=user_id, organization_id=organization_id, mode=mode, course_id=course_id, version_id=version_id)
        self.db.add(conversation)
        await self.db.commit()
        return conversation

    async def get_owned(self, public_id: int, user_id: int, *, messages: bool = False) -> Conversation:
        stmt = select(Conversation).where(Conversation.public_id == public_id, Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
        if messages:
            stmt = stmt.options(selectinload(Conversation.messages))
        conversation = (await self.db.execute(stmt)).scalar_one_or_none()
        if conversation is None:
            raise NotFoundError("Conversation not found.", code="CONVERSATION_NOT_FOUND")
        return conversation

    async def delete(self, conversation: Conversation) -> None:
        conversation.deleted_at = utcnow()
        await self.db.commit()

    # ------------------------------------------------------------------ a turn

    async def _append(self, conversation: Conversation, *, role: MessageRole, kind: MessageKind, content: str, **fields: Any) -> Message:
        """Add a message under a lock on its conversation, so two concurrent posts get consecutive numbers."""
        await self.db.flush()  # the lock's refresh below must not overwrite the caller's unflushed changes to this conversation
        locked = (await self.db.execute(select(Conversation).where(Conversation.id == conversation.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        message = Message(public_id=new_public_id(), conversation_id=locked.id, seq=locked.message_count + 1, role=role, kind=kind, content=content, **fields)
        self.db.add(message)
        locked.message_count += 1
        locked.last_message_at = utcnow()
        if not locked.title and role == MessageRole.USER:
            locked.title = " ".join(content.split())[:100]
        conversation.message_count, conversation.last_message_at, conversation.title = locked.message_count, locked.last_message_at, locked.title
        await self.db.flush()
        return message

    async def _existing_turn(self, conversation: Conversation, idempotency_key: str | None) -> tuple[Message | None, Message | None]:
        if not idempotency_key:
            return None, None
        user = (await self.db.execute(select(Message).where(Message.conversation_id == conversation.id, Message.idempotency_key == idempotency_key))).scalar_one_or_none()
        if user is None:
            return None, None
        reply = (await self.db.execute(select(Message).where(Message.conversation_id == conversation.id, Message.seq == user.seq + 1, Message.role == MessageRole.ASSISTANT))).scalar_one_or_none()
        return user, reply

    def _require_open(self, conversation: Conversation) -> None:
        if conversation.status == ConversationStatus.CLOSED:
            raise ConflictError("This conversation is closed.", code="CONVERSATION_CLOSED")

    async def _practice_item(self, conversation: Conversation, context: MessageContext) -> ItemRef | None:
        if context.item_id is None:
            return None
        item = await self.db.get(ItemRef, context.item_id)
        if item is None or (conversation.course_id is not None and item.course_id != conversation.course_id):
            raise ValidationFailedError("That lesson is not part of this course.", code="ITEM_NOT_IN_COURSE")
        return item

    async def _facts(self, user_id: int, wanted: set[str]) -> str | None:
        if not wanted:
            return None
        lines: list[str] = []
        if "enrolment" in wanted:
            rows = (await self.db.execute(select(EnrollmentRef).where(EnrollmentRef.student_user_id == user_id).order_by(EnrollmentRef.updated_at.desc()).limit(10))).scalars().all()
            for r in rows:
                version = await self.db.get(CourseVersionRef, r.version_id)
                lines.append(f"- Enrolment: {version.title if version else 'a course'} — {'active' if r.active else 'removed'}")
            if not rows:
                lines.append("- Enrolment: no enrolments found.")
        if "attempts" in wanted:
            rows2 = (await self.db.execute(select(AttemptRef).where(AttemptRef.user_id == user_id).order_by(AttemptRef.updated_at.desc()).limit(5))).scalars().all()
            for a in rows2:
                outcome = f", result {a.result}" + (f" ({a.percent:.0f}%)" if a.percent is not None else "") if a.result else ""
                lines.append(f"- Test attempt ({a.test_kind or 'test'}): {a.state.replace('_', ' ')}{outcome}")
            if not rows2:
                lines.append("- Test attempts: none found.")
        if "certificates" in wanted:
            rows3 = (await self.db.execute(select(CertificateRef).where(CertificateRef.student_user_id == user_id).order_by(CertificateRef.updated_at.desc()).limit(5))).scalars().all()
            for c in rows3:
                lines.append(f"- Certificate: {c.status}" + (f", grade {c.grade}" if c.grade else ""))
            if not rows3:
                lines.append("- Certificates: none found.")
        return "\n".join(lines)

    async def _hint_level(self, user_id: int, item: ItemRef | None, text: str, context: MessageContext) -> int | None:
        """The rung of the hint ladder this answer may reach; ``None`` when the student is not on a practice problem."""
        if item is None or item.item_type != "practice":
            return None
        if not (context.hint_request or asks_for_solution(text)):
            return 0
        progress = (
            await self.db.execute(select(HintProgress).where(HintProgress.user_id == user_id, HintProgress.item_id == item.item_id).with_for_update().execution_options(populate_existing=True))
        ).scalar_one_or_none()
        if progress is None:
            progress = HintProgress(user_id=user_id, item_id=item.item_id, level=0)
            self.db.add(progress)
        decision = hints.next_level(progress.level, max_level=self.settings.MAX_HINT_LEVEL)
        progress.level = decision.level
        return decision.level

    async def _escalate(self, conversation: Conversation, reason: EscalationReason, category: EscalationCategory) -> _Immediate:
        escalation, created = await EscalationService(self.db, self.settings).open(conversation, reason=reason, category=category)
        text = CATEGORY_TEXT.get(category) if reason == EscalationReason.SENSITIVE_TOPIC else REASON_TEXT.get(reason)
        text = text or REASON_TEXT[EscalationReason.USER_REQUESTED]
        return _Immediate(MessageKind.ESCALATION, text if created else ALREADY_ESCALATED, escalation=escalation)

    async def _decide(self, conversation: Conversation, user_message: Message, context: MessageContext) -> _Decision:
        text = user_message.content
        mode = ConversationMode(conversation.mode)
        default_category = EscalationCategory.LEARNING if conversation.course_id else EscalationCategory.TECHNICAL

        category = sensitive_category(text, mode)
        if category is not None:
            conversation.low_confidence_streak = 0
            return _Decision(immediate=await self._escalate(conversation, EscalationReason.SENSITIVE_TOPIC, category))
        if asks_for_human(text):
            conversation.low_confidence_streak = 0
            return _Decision(immediate=await self._escalate(conversation, EscalationReason.USER_REQUESTED, default_category))

        item = await self._practice_item(conversation, context)
        level = await self._hint_level(conversation.user_id, item, text, context)
        await self.db.commit()  # nothing below holds a transaction open across a call to ai-gateway

        organization_id = conversation.organization_id or self.settings.PLATFORM_ORGANIZATION_ID
        try:
            vector = await self.retrieval.embed_query(organization_id=organization_id, user_id=conversation.user_id, text=text)
            faq = await self.retrieval.search_faq(organization_id=conversation.organization_id, course_id=conversation.course_id, query=text, vector=vector)
            retrieval = Retrieval([], RetrievalMethod.NONE, 0.0)
            opened = False
            if mode == ConversationMode.LEARNING and conversation.version_id is not None:
                retrieval = await self.retrieval.search_content(conversation.version_id, text, vector)
                if item is not None:  # the lesson or problem the student has open is always part of what they are asking about
                    retrieval = await self.retrieval.with_open_lesson(retrieval, conversation.version_id, item.item_id)
                    opened = item.item_id in {p.chunk.item_id for p in retrieval.passages}
        except GatewayError as exc:
            raise _map_gateway(exc) from exc

        if faq is not None and faq.score >= self.settings.FAQ_DIRECT_ANSWER_AT:
            conversation.low_confidence_streak = 0
            entry = faq.entry
            citation = {"type": "faq", "faq_id": str(entry.public_id), "question": entry.question, "score": round(faq.score, 3)}
            return _Decision(immediate=_Immediate(MessageKind.FAQ, entry.answer, citations=[citation, *(entry.citations or [])], confidence=faq.score, retrieval=retrieval.method, hint_level=level))

        wanted = lookups_wanted(text) if mode == ConversationMode.SUPPORT else set()
        facts = await self._facts(conversation.user_id, wanted)
        faq_context = faq if faq is not None and faq.score >= self.settings.MIN_RELEVANCE else None
        if mode == ConversationMode.LEARNING:
            grounded = bool(retrieval.passages) and retrieval.top_score >= self.settings.LOW_CONFIDENCE_BELOW
            grounded = grounded or bool(context.code) or faq_context is not None or opened
        else:
            grounded = faq_context is not None or bool(wanted)
        if not grounded:
            return _Decision(immediate=await self._low_confidence(conversation, retrieval, default_category, level))

        conversation.low_confidence_streak = 0
        sources = [
            SourceLine(number, self._where(p), p.chunk.text[: self.settings.CHUNK_MAX_CHARS])
            for number, p in enumerate(retrieval.passages, start=1)
        ]
        built = build_user_message(
            text, sources=sources, code=(context.code or None), language=context.language, facts=facts,
            faq=[(faq_context.entry.question, faq_context.entry.answer)] if faq_context else [],
        )[:_GATEWAY_LIMIT]
        history = await self._history(conversation, user_message)
        topic = item.topic_title if item else "the course in general"
        course_title = await self._course_title(conversation)
        if mode == ConversationMode.LEARNING:
            key, variables = self.settings.LEARNING_PROMPT_KEY, {"course_title": course_title or "this course", "topic_title": topic or "the course in general", "hint_policy": prompts.hint_policy(level or 0)}
        else:
            key, variables = self.settings.SUPPORT_PROMPT_KEY, {}
        plan = _Plan(key, variables, normalize_history(history, built, self.settings.HISTORY_MAX_CHARS), retrieval.passages, faq_context, retrieval.method, retrieval.top_score, level)
        return _Decision(plan=plan)

    async def _low_confidence(self, conversation: Conversation, retrieval: Retrieval, category: EscalationCategory, level: int | None) -> _Immediate:
        conversation.low_confidence_streak += 1
        if conversation.low_confidence_streak >= self.settings.LOW_CONFIDENCE_ESCALATE_AFTER:
            conversation.low_confidence_streak = 0
            return await self._escalate(conversation, EscalationReason.LOW_CONFIDENCE, category)
        return _Immediate(MessageKind.LOW_CONFIDENCE, LOW_CONFIDENCE_TEXT, confidence=retrieval.top_score, retrieval=retrieval.method, hint_level=level)

    @staticmethod
    def _where(passage: Passage) -> str:
        chunk = passage.chunk
        place = " > ".join(x for x in (chunk.module_title, chunk.topic_title, chunk.item_title) if x)
        return place + (f" (at {clock(chunk.start_seconds)})" if chunk.start_seconds is not None else "")

    async def _course_title(self, conversation: Conversation) -> str | None:
        if conversation.version_id is None:
            return None
        ref = await self.db.get(CourseVersionRef, conversation.version_id)
        return ref.title if ref else None

    async def _history(self, conversation: Conversation, current: Message) -> list[tuple[str, str]]:
        rows = (
            await self.db.execute(
                select(Message).where(Message.conversation_id == conversation.id, Message.seq < current.seq).order_by(Message.seq.desc()).limit(self.settings.HISTORY_MESSAGES)
            )
        ).scalars().all()
        return [(m.role, m.content) for m in reversed(rows)]

    def _citations(self, plan: _Plan, answer: str) -> list[dict[str, Any]]:
        by_number = {number: passage for number, passage in enumerate(plan.passages, start=1)}
        chosen = [n for n in cited_numbers(answer) if n in by_number]
        implicit = not chosen
        if implicit and plan.passages:
            chosen = [1]  # docs/PRODUCT.md §5.5: every answer cites where it came from; the best source stands in if the model cited none
        out: list[dict[str, Any]] = []
        for n in chosen:
            chunk, score = by_number[n].chunk, by_number[n].score
            out.append(
                {
                    "type": "lesson", "number": n, "item_id": str(chunk.item_id), "item_title": chunk.item_title, "topic_title": chunk.topic_title,
                    "module_title": chunk.module_title, "item_type": chunk.item_type, "source": chunk.source, "start_seconds": chunk.start_seconds,
                    "score": round(score, 3), "implicit": implicit,
                }
            )
        if plan.faq is not None:
            out.append({"type": "faq", "faq_id": str(plan.faq.entry.public_id), "question": plan.faq.entry.question, "score": round(plan.faq.score, 3)})
        return out

    async def _save_immediate(self, conversation: Conversation, immediate: _Immediate) -> Message:
        message = await self._append(
            conversation, role=MessageRole.ASSISTANT, kind=immediate.kind, content=immediate.content, citations=immediate.citations,
            confidence=immediate.confidence, retrieval=immediate.retrieval, hint_level=immediate.hint_level,
        )
        await self.db.commit()
        return message

    async def _save_answer(self, conversation: Conversation, plan: _Plan, completion: Completion | None, content: str, *, blocked: bool) -> Message:
        if blocked:
            message = await self._append(
                conversation, role=MessageRole.ASSISTANT, kind=MessageKind.BLOCKED, content=BLOCKED_TEXT, prompt_key=plan.prompt_key,
                gateway_call_id=completion.call_id if completion else None, guardrail_flags=completion.guardrail_flags if completion else None,
            )
        else:
            message = await self._append(
                conversation, role=MessageRole.ASSISTANT, kind=MessageKind.ANSWER, content=content, citations=self._citations(plan, content),
                confidence=plan.top_score, retrieval=plan.method, prompt_key=plan.prompt_key, hint_level=plan.hint_level,
                gateway_call_id=completion.call_id if completion else None, guardrail_flags=completion.guardrail_flags if completion else None,
            )
        await self.db.commit()
        return message

    async def _begin(self, conversation: Conversation, content: str, context: MessageContext, idempotency_key: str | None) -> tuple[Message, Message | None]:
        """Guard, de-duplicate and save the student's message. Returns ``(user_message, existing_reply)``."""
        self._require_open(conversation)
        attempt = await self._blocking_attempt(conversation.user_id)
        if attempt is not None:
            raise TutorDisabledError(
                "The tutor is switched off while you are taking a graded test. It will be back as soon as you submit.", code="TUTOR_DISABLED_IN_TEST"
            )
        user, reply = await self._existing_turn(conversation, idempotency_key)
        if user is not None:
            return user, reply
        message = await self._append(
            conversation, role=MessageRole.USER, kind=MessageKind.QUESTION, content=content, context=context.as_json(), idempotency_key=idempotency_key
        )
        await self.db.commit()  # the message is kept whatever happens next
        return message, None

    async def hand_over(self, conversation: Conversation) -> Turn:
        """The student pressed "talk to a person": the same hand-off as asking for one in words, without a model."""
        self._require_open(conversation)
        default = EscalationCategory.LEARNING if conversation.course_id else EscalationCategory.TECHNICAL
        user_message = await self._append(conversation, role=MessageRole.USER, kind=MessageKind.QUESTION, content="I'd like to talk to a person.", context={"button": "escalate"})
        immediate = await self._escalate(conversation, EscalationReason.USER_REQUESTED, default)
        assistant = await self._save_immediate(conversation, immediate)
        return Turn(user_message, assistant, immediate.escalation)

    async def send(self, conversation: Conversation, content: str, context: MessageContext, idempotency_key: str | None = None) -> Turn:
        user_message, reply = await self._begin(conversation, content, context, idempotency_key)
        if reply is not None:
            return Turn(user_message, reply)
        decision = await self._decide(conversation, user_message, context)
        if decision.immediate is not None:
            assistant = await self._save_immediate(conversation, decision.immediate)
            return Turn(user_message, assistant, decision.immediate.escalation)
        plan = decision.plan
        assert plan is not None
        await self.db.commit()
        try:
            completion = await self.gateway.complete(
                organization_id=conversation.organization_id or self.settings.PLATFORM_ORGANIZATION_ID, user_id=conversation.user_id, prompt_key=plan.prompt_key,
                variables=plan.variables, messages=plan.messages, idempotency_key=f"tutor:{user_message.public_id}",
            )
        except GatewayError as exc:
            raise _map_gateway(exc) from exc
        assistant = await self._save_answer(conversation, plan, completion, completion.content, blocked=completion.status == "blocked")
        return Turn(user_message, assistant)

    async def send_stream(self, conversation: Conversation, content: str, context: MessageContext, idempotency_key: str | None = None) -> tuple[Message, Message | None, AsyncIterator[dict[str, Any]] | None]:
        """Like ``send`` but the answer is streamed. Everything that can fail with a normal HTTP error (a disabled tutor, a
        missing enrolment, an exhausted quota) is raised here, *before* a streaming response starts. Returns the saved
        student message, the finished assistant message when no model is involved (an escalation, a FAQ answer, a low-confidence
        reply) or a replay, and otherwise the generator that streams the answer and saves it."""
        user_message, reply = await self._begin(conversation, content, context, idempotency_key)
        if reply is not None:
            return user_message, reply, None
        decision = await self._decide(conversation, user_message, context)
        if decision.immediate is not None:
            return user_message, await self._save_immediate(conversation, decision.immediate), None
        plan = decision.plan
        assert plan is not None
        await self.db.commit()
        return user_message, None, self._stream(conversation, plan)

    async def _stream(self, conversation: Conversation, plan: _Plan) -> AsyncIterator[dict[str, Any]]:
        parts: list[str] = []
        completion: Completion | None = None
        blocked = False
        try:
            async for event in self.gateway.stream(
                organization_id=conversation.organization_id or self.settings.PLATFORM_ORGANIZATION_ID, user_id=conversation.user_id,
                prompt_key=plan.prompt_key, variables=plan.variables, messages=plan.messages,
            ):
                kind = event.get("type")
                if kind == "delta":
                    parts.append(event["text"])
                    yield {"type": "delta", "text": event["text"]}
                elif kind == "blocked":
                    blocked = True
                    completion = Completion(event.get("call_id"), "blocked", "", None, list(event.get("guardrail_flags", [])))
                elif kind == "usage":
                    completion = Completion(int(event["call_id"]) if event.get("call_id") else None, "ok", "", event.get("model"))
                elif kind == "error":
                    raise GatewayUnavailable(str(event.get("code")))
        except GatewayError as exc:
            mapped = _map_gateway(exc)
            yield {"type": "error", "code": getattr(mapped, "code", "TUTOR_UNAVAILABLE"), "message": getattr(mapped, "message", "The tutor cannot answer right now.")}
            return
        message = await self._save_answer(conversation, plan, completion, "".join(parts), blocked=blocked)
        yield {"type": "done", "message": message}
