"""The student's side of support: open a ticket, follow it, reply, close it, rate it. Internal notes are never returned here."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentAuth,
    DbSession,
    IdempotencyKeyHeader,
    MessageIdParam,
    ReplyRateLimit,
    RequireStudent,
    RequireTicketOpener,
    SettingsDep,
    TicketIdParam,
    TicketRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError
from app.core.security import AccessTokenClaims
from app.domain.enums import Source
from app.models.config import UserRef
from app.models.ticket import Ticket
from app.permissions import policy
from app.schemas.support import (
    AttachmentLink,
    AttachmentLinkResponse,
    CsatRequest,
    MessageOut,
    MessageResponse,
    ReplyCreate,
    TicketCreate,
    TicketDetailResponse,
    TicketOut,
    TicketPageResponse,
    TicketResponse,
)
from app.services.attachment_service import AttachmentService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets (student)"])


async def present_detail(db: AsyncSession, service: TicketService, ticket: Ticket, *, include_internal: bool) -> TicketDetailResponse:
    messages = await service.messages(ticket, include_internal=include_internal)
    requester = await db.get(UserRef, ticket.requester_user_id)
    assignee = await db.get(UserRef, ticket.assignee_user_id) if ticket.assignee_user_id else None

    def name(ref: UserRef | None) -> str | None:
        return (f"{ref.first_name} {ref.last_name}".strip() or None) if ref else None

    return TicketDetailResponse(
        message="", ticket=TicketOut.model_validate(ticket), messages=[MessageOut.model_validate(m) for m in messages],
        requester_name=name(requester), assignee_name=name(assignee),
    )


async def load_visible(service: TicketService, auth: AccessTokenClaims, ticket_id: int) -> Ticket:
    ticket = await service.get(ticket_id)
    if not policy.can_view(auth, ticket):
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")  # not revealing that it exists
    return ticket


async def load_own(service: TicketService, auth: AccessTokenClaims, ticket_id: int) -> Ticket:
    ticket = await service.get(ticket_id)
    if ticket.requester_user_id != auth.user_id:
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    return ticket


@router.post(
    "", response_model=TicketResponse, status_code=201, summary="Open a ticket",
    description="Routed by category: learning doubts to your institution's staff, technical/billing/access to platform support, "
    "integrity to the exam team. An `Idempotency-Key` makes a retried request return the same ticket.",
    responses=errors(*AUTHENTICATED), dependencies=[TicketRateLimit],
)
async def create_ticket(body: TicketCreate, auth: RequireTicketOpener, db: DbSession, settings: SettingsDep, key: IdempotencyKeyHeader = None) -> TicketResponse:
    attachments = await AttachmentService(settings).verify(auth.user_id, body.attachments)
    ticket, created = await TicketService(db, settings).create(
        requester_user_id=auth.user_id, organization_id=auth.organization_id, subject=body.subject, description=body.description,
        category=body.category, source=Source.PORTAL, course_id=body.course_id, idempotency_key=f"portal:{auth.user_id}:{key}" if key else None,
        attachments=attachments,
    )
    await db.commit()
    return TicketResponse(message="Ticket opened." if created else "Ticket already opened.", ticket=TicketOut.model_validate(ticket))


@router.get("", response_model=TicketPageResponse, summary="My tickets", responses=errors(*AUTHENTICATED))
async def my_tickets(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, status: Annotated[str | None, Query(max_length=20)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketPageResponse:
    tickets, total, exact = await TicketService(db, settings).list_mine(auth.user_id, status=status, page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=exact, sort_column="created_at", sort_order=SortOrder.DESC)
    return TicketPageResponse(message="", tickets=[TicketOut.model_validate(t) for t in tickets], page_context=context)


@router.get("/{ticket_id}", response_model=TicketDetailResponse, summary="One of my tickets, with its conversation", responses=errors(*AUTHENTICATED, 404))
async def get_ticket(ticket_id: TicketIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TicketDetailResponse:
    service = TicketService(db, settings)
    ticket = await load_own(service, auth, ticket_id)
    return await present_detail(db, service, ticket, include_internal=False)


@router.post(
    "/{ticket_id}/replies", response_model=MessageResponse, status_code=201, summary="Reply on my ticket",
    description="Replying to a resolved ticket reopens it (within the reopen window). A closed ticket cannot be replied to.",
    responses=errors(*AUTHENTICATED, 404, 409), dependencies=[ReplyRateLimit],
)
async def reply(ticket_id: TicketIdParam, body: ReplyCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> MessageResponse:
    service = TicketService(db, settings)
    attachments = await AttachmentService(settings).verify(auth.user_id, body.attachments)
    ticket, message = await service.reply_as_requester(await load_own(service, auth, ticket_id), auth.user_id, body.body, attachments)
    return MessageResponse(message="Reply sent.", ticket=TicketOut.model_validate(ticket), reply=MessageOut.model_validate(message))


@router.get(
    "/{ticket_id}/messages/{message_id}/attachments/{index}", response_model=AttachmentLinkResponse, summary="Download an attachment on my ticket",
    description="A short-lived link (`S3_DOWNLOAD_URL_EXPIRES_SECONDS`) to the file; `index` is its position in the message's `attachments`.",
    responses=errors(*AUTHENTICATED, 404),
)
async def attachment(ticket_id: TicketIdParam, message_id: MessageIdParam, index: int, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> AttachmentLinkResponse:
    service = TicketService(db, settings)
    message = await service.message(await load_own(service, auth, ticket_id), message_id, include_internal=False)
    return AttachmentLinkResponse(message="", attachment=AttachmentLink.model_validate(await AttachmentService(settings).download_url(message, index)))


@router.post("/{ticket_id}/close", response_model=TicketResponse, summary="Close my ticket", responses=errors(*AUTHENTICATED, 404))
async def close_ticket(ticket_id: TicketIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    ticket = await service.close_as_requester(await load_own(service, auth, ticket_id), auth.user_id)
    return TicketResponse(message="Ticket closed.", ticket=TicketOut.model_validate(ticket))


@router.post(
    "/{ticket_id}/csat", response_model=TicketResponse, summary="Rate the support I received",
    description="Once per ticket, after it is resolved or closed. 1 (poor) to 5 (excellent).", responses=errors(*AUTHENTICATED, 404, 409),
)
async def csat(ticket_id: TicketIdParam, body: CsatRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    ticket = await service.submit_csat(await load_own(service, auth, ticket_id), auth.user_id, body.rating, body.comment)
    return TicketResponse(message="Thanks for the feedback.", ticket=TicketOut.model_validate(ticket))
