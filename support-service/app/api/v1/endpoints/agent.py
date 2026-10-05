"""The agent's side: queues, ticket handling, canned replies, SLA policies and reports.

Batch-staff tickets are handled by the requester's own institution's staff; exam-team tickets by ``exams.manage``; a
``support.manage`` holder handles everything.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    AgentRateLimit,
    CannedIdParam,
    DbSession,
    IdempotencyKeyHeader,
    RequireAgent,
    RequireInternalCaller,
    RequireManager,
    SettingsDep,
    TicketIdParam,
    TutorClientDep,
)
from app.api.responses import AUTHENTICATED, errors
from app.api.v1.endpoints.tickets import load_visible, present_detail
from app.clients.tutor import TranscriptNotFound, TutorUnavailable
from app.core.exceptions import NotFoundError, UpstreamUnavailableError, ValidationFailedError
from app.core.ids import parse_public_id
from app.core.time import utcnow
from app.domain.enums import Priority, Queue, Source, TicketStatus
from app.models.ticket import Ticket
from app.permissions import policy
from app.schemas.support import (
    AgentReplyCreate,
    AssigneeOut,
    AssigneesResponse,
    AssignRequest,
    CannedCreate,
    CannedListResponse,
    CannedOut,
    CannedResponse,
    CannedUpdate,
    EventsResponse,
    InternalTicketCreate,
    InternalTicketOut,
    InternalTicketResponse,
    MessageOut,
    MessageResponse,
    RenderedCanned,
    RenderedCannedResponse,
    SlaPoliciesResponse,
    SlaPolicyUpsert,
    SlaReportOut,
    SlaReportResponse,
    SummaryResponse,
    TicketDetailResponse,
    TicketEventOut,
    TicketOut,
    TicketPageResponse,
    TicketResponse,
    TicketUpdate,
    TranscriptOut,
    TranscriptResponse,
)
from app.services.config_service import ConfigService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/agent", tags=["Agent"], dependencies=[AgentRateLimit])
admin = APIRouter(prefix="/admin", tags=["Support administration"])
internal = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[RequireInternalCaller])


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


# ---------------------------------------------------------------- queues
@router.get(
    "/tickets", response_model=TicketPageResponse, summary="The ticket queue",
    description="The tickets this agent may see, active ones by default. `assignee` is `me`, `unassigned`, or a user id; `sort` is `due` (most urgent first), `activity` or `created`.",
    responses=errors(*AUTHENTICATED),
)
async def list_queue(
    auth: RequireAgent, db: DbSession, settings: SettingsDep, status: Annotated[TicketStatus | None, Query()] = None, queue: Annotated[Queue | None, Query()] = None,
    priority: Annotated[Priority | None, Query()] = None, category: Annotated[str | None, Query(max_length=12)] = None, assignee: Annotated[str | None, Query(max_length=20)] = None,
    breached: Annotated[bool | None, Query()] = None, q: Annotated[str | None, Query(max_length=100)] = None, course_id: Annotated[str | None, Query()] = None,
    requester_id: Annotated[str | None, Query()] = None, sort: Annotated[str, Query(pattern="^(due|activity|created)$")] = "due",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketPageResponse:
    if assignee not in (None, "me", "unassigned") and parse_public_id(assignee or "") is None:
        raise ValidationFailedError(details=[{"field": "assignee", "code": "INVALID_ID", "message": "Use me, unassigned or a user id"}])
    tickets, total, exact = await TicketService(db, settings).list_queue(
        auth, status=status.value if status else None, queue=queue.value if queue else None, priority=priority.value if priority else None, category=category,
        assignee=assignee if assignee in (None, "me", "unassigned") else str(parse_public_id(assignee or "")), breached=breached, q=q,
        course_id=parse_public_id(course_id) if course_id else None, requester=parse_public_id(requester_id) if requester_id else None, sort=sort, page=page, per_page=per_page,
    )
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=exact, sort_column=sort, sort_order=SortOrder.ASC if sort == "due" else SortOrder.DESC)
    return TicketPageResponse(message="", tickets=[TicketOut.model_validate(t) for t in tickets], page_context=context)


@router.get("/tickets/summary", response_model=SummaryResponse, summary="Queue counts and the oldest unanswered ticket", responses=errors(*AUTHENTICATED))
async def summary(auth: RequireAgent, db: DbSession, settings: SettingsDep) -> SummaryResponse:
    data = await TicketService(db, settings).summary(auth)
    return SummaryResponse.model_validate({"message": "", **data})


@router.get("/reports/sla", response_model=SlaReportResponse, summary="SLA compliance, response times and CSAT over a period", responses=errors(*AUTHENTICATED))
async def sla_report(
    auth: RequireAgent, db: DbSession, settings: SettingsDep, start: Annotated[datetime | None, Query()] = None, end: Annotated[datetime | None, Query()] = None
) -> SlaReportResponse:
    end_at = _aware(end) if end else utcnow()
    start_at = _aware(start) if start else end_at - timedelta(days=30)
    if start_at >= end_at:
        raise ValidationFailedError(details=[{"field": "start", "code": "INVALID_RANGE", "message": "start must be before end"}])
    return SlaReportResponse(message="", report=SlaReportOut.model_validate(await TicketService(db, settings).sla_report(auth, start=start_at, end=end_at)))


# ---------------------------------------------------------------- one ticket
@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse, summary="A ticket with its conversation and internal notes", responses=errors(*AUTHENTICATED, 404))
async def get_ticket(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketDetailResponse:
    service = TicketService(db, settings)
    ticket = await load_visible(service, auth, ticket_id)
    if not policy.can_handle(auth, ticket):
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    return await present_detail(db, service, ticket, include_internal=True)


@router.get(
    "/tickets/{ticket_id}/transcript", response_model=TranscriptResponse, summary="The tutor conversation a ticket was handed off from",
    description="Only for a ticket opened by ai-tutor (source `ai-tutor`); read from ai-tutor-service with the internal token once "
    "this service has decided the agent may handle the ticket. `404 NO_TRANSCRIPT` otherwise or if the student deleted it, "
    "`502 UPSTREAM_UNAVAILABLE` when ai-tutor does not answer.",
    responses=errors(*AUTHENTICATED, 404, 502),
)
async def ticket_transcript(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep, tutor: TutorClientDep) -> TranscriptResponse:
    ticket = await load_visible(TicketService(db, settings), auth, ticket_id)
    if not policy.can_handle(auth, ticket):
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    if ticket.source != Source.AI_TUTOR or not ticket.source_ref:
        raise NotFoundError("This ticket was not handed off from the tutor.", code="NO_TRANSCRIPT")
    try:
        conversation = await tutor.transcript(ticket.source_ref)
    except TranscriptNotFound as exc:
        raise NotFoundError("The tutor conversation no longer exists.", code="NO_TRANSCRIPT") from exc
    except TutorUnavailable as exc:
        raise UpstreamUnavailableError("The tutor service is not answering; try again shortly.") from exc
    return TranscriptResponse(message="", transcript=TranscriptOut.model_validate(conversation))


@router.get(
    "/tickets/{ticket_id}/assignees", response_model=AssigneesResponse, summary="Who this ticket may be assigned to",
    description="For someone who may assign it to another person (a support manager, or the head for their institution's batch_staff "
    "queue): the active people of the ticket's queue — the same rule `POST .../assign` enforces.",
    responses=errors(*AUTHENTICATED, 404),
)
async def ticket_assignees(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> AssigneesResponse:
    service = TicketService(db, settings)
    ticket = await load_visible(service, auth, ticket_id)
    if not policy.can_handle(auth, ticket):
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    people = await service.assignees(ticket, auth)
    return AssigneesResponse(
        message="",
        assignees=[AssigneeOut(user_id=str(p.user_id), name=f"{p.first_name} {p.last_name}".strip() or str(p.user_id), role=p.role) for p in people],
    )


@router.get("/tickets/{ticket_id}/events", response_model=EventsResponse, summary="The audit trail of a ticket", responses=errors(*AUTHENTICATED, 404))
async def ticket_events(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> EventsResponse:
    service = TicketService(db, settings)
    ticket = await load_visible(service, auth, ticket_id)
    if not policy.can_handle(auth, ticket):
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    return EventsResponse(message="", events=[TicketEventOut.model_validate(e) for e in await service.events(ticket)])


async def _handled(service: TicketService, auth: RequireAgent, ticket_id: int) -> Ticket:
    ticket = await load_visible(service, auth, ticket_id)
    if not policy.can_handle(auth, ticket):
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    return ticket


@router.post(
    "/tickets/{ticket_id}/replies", response_model=MessageResponse, status_code=201, summary="Reply to the student, or leave an internal note",
    description="A public reply is the first response for SLA purposes and assigns the ticket to the replier if nobody has it. "
    "`then` may move the ticket to `waiting_on_student` (pauses the SLA clock) or `resolved`.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def reply(ticket_id: TicketIdParam, body: AgentReplyCreate, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> MessageResponse:
    service = TicketService(db, settings)
    ticket = await _handled(service, auth, ticket_id)
    if body.then not in (None, TicketStatus.WAITING_ON_STUDENT, TicketStatus.RESOLVED):
        raise ValidationFailedError(details=[{"field": "then", "code": "INVALID_STATUS", "message": "Use waiting_on_student or resolved"}])
    ticket, message = await service.reply_as_agent(
        ticket, auth, body=body.body, internal=body.internal, then=body.then.value if body.then else None, canned_reply_id=body.canned_reply_id
    )
    return MessageResponse(message="Note added." if body.internal else "Reply sent.", ticket=TicketOut.model_validate(ticket), reply=MessageOut.model_validate(message))


@router.post("/tickets/{ticket_id}/claim", response_model=TicketResponse, summary="Take a ticket", responses=errors(*AUTHENTICATED, 404, 409))
async def claim(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    return TicketResponse(message="Ticket claimed.", ticket=TicketOut.model_validate(await service.claim(await _handled(service, auth, ticket_id), auth)))


@router.post(
    "/tickets/{ticket_id}/assign", response_model=TicketResponse, summary="Assign a ticket to someone",
    description="A support manager anywhere; an institution head within their own institution's queue. The assignee must be able to handle the queue.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def assign(ticket_id: TicketIdParam, body: AssignRequest, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    ticket = await service.assign(await _handled(service, auth, ticket_id), auth, body.assignee_user_id)
    return TicketResponse(message="Ticket assigned.", ticket=TicketOut.model_validate(ticket))


@router.post("/tickets/{ticket_id}/release", response_model=TicketResponse, summary="Hand a ticket back to its queue", responses=errors(*AUTHENTICATED, 404))
async def release(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    return TicketResponse(message="Ticket released.", ticket=TicketOut.model_validate(await service.release(await _handled(service, auth, ticket_id), auth)))


@router.patch(
    "/tickets/{ticket_id}", response_model=TicketResponse, summary="Change priority or category",
    description="Changing the priority recomputes the SLA due times. Changing the category may move the ticket to another queue, where it starts unassigned.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def update(ticket_id: TicketIdParam, body: TicketUpdate, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    ticket = await service.update(await _handled(service, auth, ticket_id), auth, priority=body.priority, category=body.category)
    return TicketResponse(message="Ticket updated.", ticket=TicketOut.model_validate(ticket))


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketResponse, summary="Mark resolved (asks the student for a CSAT rating)", responses=errors(*AUTHENTICATED, 404, 409))
async def resolve(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    return TicketResponse(message="Ticket resolved.", ticket=TicketOut.model_validate(await service.resolve(await _handled(service, auth, ticket_id), auth)))


@router.post("/tickets/{ticket_id}/reopen", response_model=TicketResponse, summary="Reopen a resolved ticket", responses=errors(*AUTHENTICATED, 404, 409))
async def reopen(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    return TicketResponse(message="Ticket reopened.", ticket=TicketOut.model_validate(await service.reopen(await _handled(service, auth, ticket_id), auth)))


@router.post("/tickets/{ticket_id}/close", response_model=TicketResponse, summary="Close a ticket", responses=errors(*AUTHENTICATED, 404))
async def close(ticket_id: TicketIdParam, auth: RequireAgent, db: DbSession, settings: SettingsDep) -> TicketResponse:
    service = TicketService(db, settings)
    return TicketResponse(message="Ticket closed.", ticket=TicketOut.model_validate(await service.close(await _handled(service, auth, ticket_id), auth)))


# ---------------------------------------------------------------- canned replies
@router.get("/canned-replies", response_model=CannedListResponse, summary="Saved replies I may use", responses=errors(*AUTHENTICATED))
async def list_canned(auth: RequireAgent, db: DbSession, include_inactive: bool = False) -> CannedListResponse:
    return CannedListResponse(message="", canned_replies=[CannedOut.model_validate(r) for r in await ConfigService(db).list_canned(auth, include_inactive=include_inactive)])


@router.post("/canned-replies", response_model=CannedResponse, status_code=201, summary="Save a reply", responses=errors(*AUTHENTICATED))
async def create_canned(body: CannedCreate, auth: RequireAgent, db: DbSession) -> CannedResponse:
    return CannedResponse(message="Saved.", canned_reply=CannedOut.model_validate(await ConfigService(db).create_canned(auth, scope=body.scope, title=body.title, body=body.body)))


@router.patch("/canned-replies/{canned_id}", response_model=CannedResponse, summary="Edit or deactivate a saved reply", responses=errors(*AUTHENTICATED, 404))
async def update_canned(canned_id: CannedIdParam, body: CannedUpdate, auth: RequireAgent, db: DbSession) -> CannedResponse:
    service = ConfigService(db)
    reply = await service.get_canned(canned_id)
    service.authorize_canned(auth, reply)
    return CannedResponse(message="Saved.", canned_reply=CannedOut.model_validate(await service.update_canned(reply, title=body.title, body=body.body, active=body.active)))


@router.get(
    "/canned-replies/{canned_id}/render", response_model=RenderedCannedResponse, summary="A saved reply filled in for a ticket",
    description="Replaces `{{student_first_name}}` and `{{ticket_subject}}`. Insert the result into a reply and edit it before sending.", responses=errors(*AUTHENTICATED, 404),
)
async def render_canned(canned_id: CannedIdParam, ticket_id: Annotated[str, Query()], auth: RequireAgent, db: DbSession, settings: SettingsDep) -> RenderedCannedResponse:
    number = parse_public_id(ticket_id)
    if number is None:
        raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
    service = TicketService(db, settings)
    ticket = await _handled(service, auth, number)
    config = ConfigService(db)
    reply = await config.get_canned(canned_id)
    if reply.scope == "organization" and reply.organization_id != ticket.organization_id and not policy.is_manager(auth):
        raise NotFoundError("Canned reply not found.", code="CANNED_REPLY_NOT_FOUND")
    return RenderedCannedResponse(message="", rendered=RenderedCanned(body=await service.render_canned(reply, ticket)))


# ---------------------------------------------------------------- SLA policies (support managers)
@admin.get("/sla-policies", response_model=SlaPoliciesResponse, summary="SLA targets per queue and priority (defaults unless overridden)", responses=errors(*AUTHENTICATED))
async def sla_policies(_: RequireManager, db: DbSession) -> SlaPoliciesResponse:
    return SlaPoliciesResponse.model_validate({"message": "", "policies": await ConfigService(db).policies()})


@admin.put(
    "/sla-policies", response_model=SlaPoliciesResponse, summary="Override an SLA target",
    description="Applies to tickets created or re-prioritised from now on; existing tickets keep their due times until they change.", responses=errors(*AUTHENTICATED, 409),
)
async def put_sla_policy(body: SlaPolicyUpsert, auth: RequireManager, db: DbSession) -> SlaPoliciesResponse:
    service = ConfigService(db)
    await service.upsert_policy(auth.user_id, queue=body.queue, priority=body.priority, first_response_minutes=body.first_response_minutes, resolution_minutes=body.resolution_minutes)
    return SlaPoliciesResponse.model_validate({"message": "Saved.", "policies": await service.policies()})


@admin.delete("/sla-policies/{queue}/{priority}", response_model=SlaPoliciesResponse, summary="Go back to the default target", responses=errors(*AUTHENTICATED))
async def reset_sla_policy(queue: Queue, priority: Priority, _: RequireManager, db: DbSession) -> SlaPoliciesResponse:
    service = ConfigService(db)
    await service.reset_policy(queue, priority)
    return SlaPoliciesResponse.model_validate({"message": "Reset.", "policies": await service.policies()})


# ---------------------------------------------------------------- internal
@internal.post(
    "/tickets", response_model=InternalTicketResponse, status_code=201, summary="Open a ticket for a student (ai-tutor-service's hand-off)",
    description="Requires `X-Internal-Service-Token`. `Idempotency-Key` makes a retry return the ticket already opened.", responses=errors(403, 422),
)
async def create_internal(body: InternalTicketCreate, db: DbSession, settings: SettingsDep, key: IdempotencyKeyHeader = None) -> InternalTicketResponse:
    ticket, created = await TicketService(db, settings).create(
        requester_user_id=body.requester_user_id, organization_id=body.organization_id, subject=body.subject, description=body.description, category=body.category,
        source=body.source, source_ref=body.source_ref, course_id=body.course_id, idempotency_key=f"internal:{key}" if key else None, reason=body.reason,
    )
    await db.commit()
    return InternalTicketResponse(message="Ticket opened." if created else "Ticket already opened.", ticket=InternalTicketOut.model_validate(ticket))
