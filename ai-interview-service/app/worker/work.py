"""Running the durable work items (see app/services/work_service.py): claim a batch, run each, finish it or retry it with backoff."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.errors import Unavailable
from app.clients.gateway import GatewayClient
from app.core.config import Settings
from app.core.exceptions import AppError
from app.domain.enums import WorkKind
from app.models.work import WorkItem
from app.services import work_service
from app.services.evaluation_service import EvaluationService
from app.services.interview_service import InterviewService

logger = logging.getLogger("app.worker.work")


async def _run(db: AsyncSession, settings: Settings, item: WorkItem, gateway: GatewayClient) -> None:
    kind = WorkKind(item.kind)
    if kind == WorkKind.EVALUATE:
        await EvaluationService(db, settings, gateway).evaluate(item.ref_id, force=bool((item.payload or {}).get("force")))
    elif kind == WorkKind.CREATE_SCREENING:
        await InterviewService(db, settings).create_screening(item.payload)
        await db.commit()


async def run_due(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, gateway: GatewayClient) -> int:
    """Run the work that is due. Returns how many items were attempted."""
    async with sessionmaker() as db:
        items = await work_service.claim(db, settings)
    for item in items:
        item_id, attempts, kind, ref_id = item.id, item.attempts, item.kind, item.ref_id
        async with sessionmaker() as db:
            try:
                await _run(db, settings, item, gateway)
            except Unavailable as exc:
                await db.rollback()
                if kind == WorkKind.EVALUATE and attempts >= settings.WORK_MAX_ATTEMPTS:
                    await EvaluationService(db, settings, gateway).mark_failed(ref_id, str(exc))
                await work_service.fail(db, settings, item_id, attempts, str(exc))
                logger.warning("work item will be retried", extra={"extra_fields": {"kind": kind, "attempts": attempts, "error": str(exc)}})
                continue
            except AppError as exc:  # a refusal that repeating cannot fix (the job names a plan that is not there)
                await db.rollback()
                await work_service.fail(db, settings, item_id, attempts, f"{exc.code}: {exc.message}", permanent=True)
                continue
            except Exception as exc:
                await db.rollback()
                logger.exception("work item failed")
                await work_service.fail(db, settings, item_id, attempts, f"{exc.__class__.__name__}: {exc}")
                continue
            await work_service.finish(db, item_id)
    return len(items)
