"""The student's side: conversations with the tutor (docs/PRODUCT.md §5.5)."""

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import func, select

from app.api.deps import (
    ConversationIdParam,
    ConversationRateLimit,
    DbSession,
    GatewayDep,
    IdempotencyKeyHeader,
    IndexCacheDep,
    MessageIdParam,
    MessageRateLimit,
    RequireStudent,
    SettingsDep,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.ids import parse_public_id
from app.models.conversation import Conversation
from app.rag.index_cache import IndexCache
from app.schemas.admin import FaqListResponse, FaqOut
from app.schemas.tutor import (
    AvailabilityOut,
    AvailabilityResponse,
    ConversationCreate,
    ConversationDetailOut,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationOut,
    ConversationResponse,
    EscalationBrief,
    FeedbackIn,
    FeedbackOut,
    FeedbackResponse,
    MessageIn,
    MessageOut,
    TurnOut,
    TurnResponse,
)
from app.services.faq_service import FaqService
from app.services.feedback_service import FeedbackService
from app.services.retrieval_service import RetrievalService
from app.services.tutor_service import MessageContext, Turn, TutorService

router = APIRouter(tags=["Tutor"])


def _service(db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCache) -> TutorService:
    return TutorService(db, settings, gateway, RetrievalService(db, settings, gateway, cache))


def _turn_out(turn: Turn) -> TurnOut:
    return TurnOut(
        user_message=MessageOut.model_validate(turn.user_message),
        assistant_message=MessageOut.model_validate(turn.assistant_message),
        escalation=EscalationBrief.model_validate(turn.escalation) if turn.escalation else None,
    )


def _line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, separators=(",", ":")) + "\n").encode()


@router.get("/availability", response_model=AvailabilityResponse, summary="Can I use the tutor right now?", responses=errors(*AUTHENTICATED))
async def availability(auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> AvailabilityResponse:
    result = await _service(db, settings, gateway, cache).availability(auth.user_id)
    return AvailabilityResponse(message="", availability=AvailabilityOut(enabled=result.enabled, reason=result.reason, attempt_id=result.attempt_id, blocked_until=result.blocked_until))


@router.post(
    "/conversations", response_model=ConversationResponse, status_code=201, dependencies=[ConversationRateLimit], summary="Start a conversation",
    description="`mode: learning` needs a `course_id` you are enrolled in; `mode: support` is the platform-support assistant.",
    responses=errors(*AUTHENTICATED, 404),
)
async def create_conversation(body: ConversationCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> ConversationResponse:
    conversation = await _service(db, settings, gateway, cache).start(user_id=auth.user_id, organization_id=auth.organization_id, mode=body.mode, course_id=body.course_id)
    return ConversationResponse(message="Conversation started.", conversation=ConversationOut.model_validate(conversation))


@router.get("/conversations", response_model=ConversationListResponse, summary="My conversations", responses=errors(*AUTHENTICATED))
async def list_conversations(
    auth: RequireStudent, db: DbSession, page: Annotated[int, Query(ge=1, le=1_000)] = 1, per_page: Annotated[int, Query(ge=1, le=50)] = 20
) -> ConversationListResponse:
    where = (Conversation.user_id == auth.user_id, Conversation.deleted_at.is_(None))
    total = int((await db.execute(select(func.count(Conversation.id)).where(*where))).scalar_one())
    rows = (
        await db.execute(select(Conversation).where(*where).order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc()).limit(per_page).offset((page - 1) * per_page))
    ).scalars().all()
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="last_message_at", sort_order=SortOrder.DESC)
    return ConversationListResponse(message="", conversations=[ConversationOut.model_validate(c) for c in rows], page_context=context)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse, summary="A conversation with its messages", responses=errors(*AUTHENTICATED, 404))
async def get_conversation(conversation_id: ConversationIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> ConversationDetailResponse:
    conversation = await _service(db, settings, gateway, cache).get_owned(conversation_id, auth.user_id, messages=True)
    detail = ConversationDetailOut.model_validate(conversation)
    return ConversationDetailResponse(message="", conversation=detail)


@router.delete("/conversations/{conversation_id}", status_code=204, summary="Delete a conversation", responses=errors(*AUTHENTICATED, 404))
async def delete_conversation(conversation_id: ConversationIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> None:
    service = _service(db, settings, gateway, cache)
    await service.delete(await service.get_owned(conversation_id, auth.user_id))


@router.post(
    "/conversations/{conversation_id}/messages", response_model=TurnResponse, dependencies=[MessageRateLimit], summary="Ask the tutor",
    description="Send an `Idempotency-Key`: a retry returns the same answer instead of asking twice. `stream: true` answers with "
    "`application/x-ndjson`: a `start` line, `delta` lines, then a final `message` line (or an `error` line). Refused with "
    "`403 TUTOR_DISABLED_IN_TEST` while a graded test is in progress. Errors that would normally be HTTP errors are still "
    "HTTP errors when streaming: they are raised before the stream starts.",
    responses=errors(*AUTHENTICATED, 404, 409, 502, 503),
)
async def post_message(
    conversation_id: ConversationIdParam, body: MessageIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep,
    idempotency_key: IdempotencyKeyHeader,
) -> TurnResponse | StreamingResponse:
    service = _service(db, settings, gateway, cache)
    conversation = await service.get_owned(conversation_id, auth.user_id)
    context = MessageContext(item_id=body.context.item_id, code=body.context.code, language=body.context.language, hint_request=body.context.hint_request)
    if not body.stream:
        turn = await service.send(conversation, body.content, context, idempotency_key)
        return TurnResponse(message="", turn=_turn_out(turn))

    user_message, reply, generator = await service.send_stream(conversation, body.content, context, idempotency_key)

    async def lines() -> AsyncIterator[bytes]:
        yield _line({"type": "start", "user_message": MessageOut.model_validate(user_message).model_dump(mode="json")})
        if reply is not None:
            yield _line({"type": "message", "message": MessageOut.model_validate(reply).model_dump(mode="json")})
            return
        assert generator is not None
        async for event in generator:
            if event["type"] == "done":
                yield _line({"type": "message", "message": MessageOut.model_validate(event["message"]).model_dump(mode="json")})
            else:
                yield _line(event)

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.post("/conversations/{conversation_id}/escalate", response_model=TurnResponse, summary="Talk to a person", responses=errors(*AUTHENTICATED, 404, 409))
async def escalate(conversation_id: ConversationIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> TurnResponse:
    service = _service(db, settings, gateway, cache)
    turn = await service.hand_over(await service.get_owned(conversation_id, auth.user_id))
    return TurnResponse(message="A person has been asked to follow up.", turn=_turn_out(turn))


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse, summary="Thumbs up or down on an answer", responses=errors(*AUTHENTICATED, 404))
async def feedback(message_id: MessageIdParam, body: FeedbackIn, auth: RequireStudent, db: DbSession) -> FeedbackResponse:
    rated, message = await FeedbackService(db).rate(user_id=auth.user_id, message_public_id=message_id, rating=body.rating, comment=body.comment)
    return FeedbackResponse(message="Thanks for the feedback.", feedback=FeedbackOut(message_id=message.public_id, rating=rated.rating, comment=rated.comment))


@router.get("/faq", response_model=FaqListResponse, summary="Published FAQ I can see", responses=errors(*AUTHENTICATED))
async def student_faq(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, q: Annotated[str | None, Query(max_length=200)] = None, course_id: Annotated[str | None, Query()] = None
) -> FaqListResponse:
    entries = await FaqService(db, settings, gateway).list_for_student(
        user_id=auth.user_id, organization_id=auth.organization_id, course_id=parse_public_id(course_id) if course_id else None, q=q
    )
    return FaqListResponse(message="", faqs=[FaqOut.model_validate(e) for e in entries])

