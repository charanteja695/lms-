"""Running the durable work items (see app/services/work_service.py): claim a batch, run each item, finish it or retry it with backoff."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.assessment import AssessmentClient
from app.clients.errors import Unavailable
from app.clients.gateway import GatewayClient
from app.core.config import Settings
from app.domain.enums import WorkKind
from app.models.work import WorkItem
from app.services import work_service
from app.services.application_events import ApplicationEvents
from app.services.match_service import MatchService
from app.services.screening_service import ScreeningService

logger = logging.getLogger("app.worker.work")


async def _run(db: AsyncSession, settings: Settings, item: WorkItem, gateway: GatewayClient, assessment: AssessmentClient) -> None:
    kind = WorkKind(item.kind)
    if kind == WorkKind.MATCH_JOB:
        await MatchService(db, settings, gateway).match_job(item.ref_id, after=int((item.payload or {}).get("after") or 0))
    elif kind == WorkKind.MATCH_CANDIDATE:
        await MatchService(db, settings, gateway).match_candidate(item.ref_id)
    elif kind == WorkKind.SCREEN:
        await ScreeningService(db, settings, gateway).screen(item.ref_id)
    elif kind == WorkKind.ASSESSMENT_INVITE:
        await ApplicationEvents(db, settings).deliver_assessment_invite(item.ref_id, assessment)


async def run_due(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, gateway: GatewayClient, assessment: AssessmentClient, *, kinds: tuple[WorkKind, ...] | None = None) -> int:
    """Run the work that is due. Returns how many items were attempted."""
    async with sessionmaker() as db:
        items = await work_service.claim(db, settings, kinds=kinds)
    for item in items:
        item_id, attempts, kind = item.id, item.attempts, item.kind
        async with sessionmaker() as db:
            try:
                await _run(db, settings, item, gateway, assessment)
            except Unavailable as exc:
                await db.rollback()
                await work_service.fail(db, settings, item_id, attempts, str(exc))
                logger.warning("work item will be retried", extra={"extra_fields": {"kind": kind, "attempts": attempts, "error": str(exc)}})
                continue
            except Exception as exc:
                await db.rollback()
                logger.exception("work item failed")
                await work_service.fail(db, settings, item_id, attempts, f"{exc.__class__.__name__}: {exc}")
                continue
            await work_service.finish(db, item_id)
    return len(items)
