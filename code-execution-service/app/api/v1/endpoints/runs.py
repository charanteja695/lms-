import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import (
    CurrentAuth,
    DbSession,
    IdempotencyKeyHeader,
    RateLimiterDep,
    RequirePractice,
    RunIdParam,
    SettingsDep,
)
from app.api.responses import errors
from app.domain.enums import JobStatus
from app.models.run import Run
from app.schemas.run import RunCreate, RunOut, RunResponse
from app.services.run_service import RunService

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.post(
    "",
    response_model=RunResponse,
    status_code=202,
    summary="Run code on custom input",
    description="Queues the run and returns at once. Read the result with GET /runs/{id} (optionally waiting) or "
    "GET /runs/{id}/stream. Send an Idempotency-Key so a retry does not run the code twice.",
    responses=errors(400, 401, 404, 422, 429),
)
async def create_run(
    data: RunCreate, auth: RequirePractice, db: DbSession, settings: SettingsDep, limiter: RateLimiterDep, key: IdempotencyKeyHeader
) -> RunResponse:
    run = await RunService(db, settings, limiter).create(auth, data, key)
    return RunResponse(message="Run queued.", run=RunOut.model_validate(run))


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="Get a run",
    description="`wait` (seconds) holds the request open until the run completes, so a client can avoid polling.",
    responses=errors(401, 404, 429),
)
async def get_run(
    run_id: RunIdParam,
    auth: CurrentAuth,
    db: DbSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    wait: Annotated[float, Query(ge=0, le=30)] = 0,
) -> RunResponse:
    service = RunService(db, settings, limiter)
    run = await service.get_for_user(run_id, auth.user_id)
    if wait and run.status != JobStatus.COMPLETED:
        run = await service.wait_until_done(run, wait)
    return RunResponse(message="Run retrieved successfully.", run=RunOut.model_validate(run))


@router.get(
    "/{run_id}/stream",
    summary="Stream a run's progress (server-sent events)",
    description="Sends a `status` event whenever the run changes and a final `done` event once it completes.",
    responses={**errors(401, 404, 429), 200: {"content": {"text/event-stream": {}}}},
)
async def stream_run(run_id: RunIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, limiter: RateLimiterDep, request: Request) -> StreamingResponse:
    await RunService(db, settings, limiter).get_for_user(run_id, auth.user_id)  # 404 before the stream starts
    await db.close()  # release the connection: the stream below polls with its own short sessions
    sessionmaker = request.app.state.sessionmaker

    async def events() -> AsyncIterator[str]:
        deadline = time.monotonic() + settings.RESULT_WAIT_MAX_SECONDS * 2
        last_status = None
        while time.monotonic() < deadline:
            async with sessionmaker() as session:  # own session: the request's closes when the handler returns
                run = (await session.execute(select(Run).where(Run.public_id == run_id))).scalar_one_or_none()
                if run is None:
                    return
                payload = RunOut.model_validate(run).model_dump_json()
                status = run.status
            if status != last_status:
                last_status = status
                yield f"event: {'done' if status == JobStatus.COMPLETED else 'status'}\ndata: {payload}\n\n"
            if status == JobStatus.COMPLETED:
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(settings.RESULT_POLL_INTERVAL_SECONDS)
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )
