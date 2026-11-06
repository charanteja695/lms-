"""FAQ management: course authors (their course), institution staff (their institution), support managers (everything)."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import select

from app.api.deps import AuthoringRateLimit, CurrentAuth, DbSession, FaqIdParam, GatewayDep, SettingsDep
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.ids import parse_public_id
from app.domain.enums import FaqScope, MessageRole
from app.models.conversation import Conversation, Message
from app.permissions.policy import can_manage_faq, can_view_conversation
from app.schemas.admin import FaqCreate, FaqOut, FaqPageResponse, FaqPromote, FaqResponse, FaqUpdate
from app.services.faq_service import FaqService

router = APIRouter(prefix="/faq/manage", tags=["FAQ"], dependencies=[AuthoringRateLimit])


@router.get("", response_model=FaqPageResponse, summary="FAQ entries I may manage", responses=errors(*AUTHENTICATED))
async def list_faq(
    auth: CurrentAuth, db: DbSession, settings: SettingsDep, gateway: GatewayDep, status: Annotated[str | None, Query(max_length=10)] = None,
    scope: Annotated[str | None, Query(max_length=14)] = None, course_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FaqPageResponse:
    entries, total, exact = await FaqService(db, settings, gateway).list_manageable(
        auth, status=status, scope=scope, course_id=parse_public_id(course_id) if course_id else None, page=page, per_page=per_page
    )
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=exact, sort_column="created_at", sort_order=SortOrder.DESC)
    return FaqPageResponse(message="", faqs=[FaqOut.model_validate(e) for e in entries], page_context=context)


@router.post("", response_model=FaqResponse, status_code=201, summary="Write a draft FAQ entry", responses=errors(*AUTHENTICATED, 409))
async def create_faq(body: FaqCreate, auth: CurrentAuth, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> FaqResponse:
    entry = await FaqService(db, settings, gateway).create(
        auth, scope=body.scope, organization_id=body.organization_id, course_id=body.course_id, question=body.question, answer=body.answer
    )
    return FaqResponse(message="Draft created.", faq=FaqOut.model_validate(entry))


@router.post(
    "/promote", response_model=FaqResponse, status_code=201, summary="Promote a tutor answer to a draft FAQ entry",
    description="Needs access to the conversation (its institution's staff, or a support manager). The draft starts as the student's "
    "question and the tutor's answer — edit it (remove anything personal) before publishing.",
    responses=errors(*AUTHENTICATED, 404),
)
async def promote(body: FaqPromote, auth: CurrentAuth, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> FaqResponse:
    row = (
        await db.execute(
            select(Message, Conversation).join(Conversation, Conversation.id == Message.conversation_id).where(Message.public_id == body.message_id, Message.role == MessageRole.ASSISTANT, Conversation.deleted_at.is_(None))
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Message not found.", code="MESSAGE_NOT_FOUND")
    answer, conversation = row
    if not can_view_conversation(auth, organization_id=conversation.organization_id):
        raise PermissionDeniedError()
    question = (await db.execute(select(Message.content).where(Message.conversation_id == conversation.id, Message.seq == answer.seq - 1))).scalar_one_or_none() or ""
    # An institution's staff write for their own institution; a course author or support manager writes for the course.
    default = FaqScope.COURSE if conversation.course_id and can_manage_faq(auth, FaqScope.COURSE, organization_id=conversation.organization_id, action="create") else FaqScope.ORGANIZATION
    scope = body.scope or default
    entry = await FaqService(db, settings, gateway).create(
        auth, scope=scope, organization_id=conversation.organization_id if scope != FaqScope.PLATFORM else None,
        course_id=conversation.course_id if scope == FaqScope.COURSE else None, question=" ".join(question.split())[:500], answer=answer.content,
        source_message_id=answer.public_id, citations=[c for c in (answer.citations or []) if c.get("type") == "lesson"],
    )
    return FaqResponse(message="Draft created from the tutor's answer.", faq=FaqOut.model_validate(entry))


@router.patch("/{faq_id}", response_model=FaqResponse, summary="Edit an entry", responses=errors(*AUTHENTICATED, 404, 409))
async def update_faq(faq_id: FaqIdParam, body: FaqUpdate, auth: CurrentAuth, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> FaqResponse:
    service = FaqService(db, settings, gateway)
    entry = await service.get(faq_id)
    service.authorize(auth, entry.scope, entry.organization_id)
    return FaqResponse(message="Entry updated.", faq=FaqOut.model_validate(await service.update(entry, question=body.question, answer=body.answer)))


@router.post("/{faq_id}/publish", response_model=FaqResponse, summary="Publish an entry", responses=errors(*AUTHENTICATED, 404, 409))
async def publish_faq(faq_id: FaqIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> FaqResponse:
    service = FaqService(db, settings, gateway)
    entry = await service.get(faq_id)
    service.authorize(auth, entry.scope, entry.organization_id)
    return FaqResponse(message="Entry published.", faq=FaqOut.model_validate(await service.publish(entry, by=auth.user_id)))


@router.post("/{faq_id}/archive", response_model=FaqResponse, summary="Archive an entry", responses=errors(*AUTHENTICATED, 404))
async def archive_faq(faq_id: FaqIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> FaqResponse:
    service = FaqService(db, settings, gateway)
    entry = await service.get(faq_id)
    service.authorize(auth, entry.scope, entry.organization_id, "delete")
    return FaqResponse(message="Entry archived.", faq=FaqOut.model_validate(await service.archive(entry)))
