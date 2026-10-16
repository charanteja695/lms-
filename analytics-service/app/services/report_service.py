"""Scheduled reports (docs/PRODUCT.md §5.9 "Scheduled reports"): a saved dashboard + filters + a schedule,
run by the worker when due. Rendering reuses the exact same dashboard functions a live `GET` uses, so a
report's numbers are never computed a second, different way."""

import csv
import io
import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import Dashboard, ReportFormat, ReportFrequency, ReportStatus
from app.models.report import ReportDefinition, ReportRun
from app.permissions.policy import Scope, can_view_platform, is_employer_member, is_institution_member, is_super_admin
from app.services import dashboard_service
from app.services.outbox import write_event

_FREQUENCY_DAYS = {ReportFrequency.DAILY: 1, ReportFrequency.WEEKLY: 7, ReportFrequency.MONTHLY: 30}
_DASHBOARD_SCOPE = {
    Dashboard.CONTENT: (Scope.CONTENT_REVIEW,), Dashboard.EXAM_INTEGRITY: (Scope.EXAMS_MANAGE,), Dashboard.SUPPORT: (Scope.SUPPORT_MANAGE,),
    Dashboard.HIRING: (Scope.CAREERS_MANAGE,), Dashboard.AI_USAGE: (Scope.AI_MANAGE,), Dashboard.BILLING: (Scope.BILLING_MANAGE,),
}


def _opt_int(value: Any) -> int | None:
    return int(value) if value not in (None, "") else None


async def run_dashboard(db: AsyncSession, dashboard: str, filters: dict[str, Any], *, since: date, until: date) -> dict[str, Any]:
    org, employer = _opt_int(filters.get("organization_id")), _opt_int(filters.get("employer_id"))
    if dashboard == Dashboard.INSTITUTION:
        if org is None:
            raise ValidationFailedError(details=[{"field": "filters.organization_id", "code": "REQUIRED", "message": "The institution dashboard needs an organization_id"}])
        return await dashboard_service.institution(db, organization_id=org, since=since, until=until)
    if dashboard == Dashboard.CONTENT:
        return await dashboard_service.content(db, since=since, until=until)
    if dashboard == Dashboard.EXAM_INTEGRITY:
        return await dashboard_service.exam_integrity(db, since=since, until=until)
    if dashboard == Dashboard.SUPPORT:
        return await dashboard_service.support(db, organization_id=org, since=since, until=until)
    if dashboard == Dashboard.HIRING:
        return await dashboard_service.hiring(db, employer_id=employer, organization_id=org, since=since, until=until)
    if dashboard == Dashboard.AI_USAGE:
        return await dashboard_service.ai_usage(db, organization_id=org, since=since, until=until)
    if dashboard == Dashboard.BILLING:
        return await dashboard_service.billing(db, organization_id=org, since=since, until=until)
    raise ValidationFailedError(details=[{"field": "dashboard", "code": "UNKNOWN_DASHBOARD", "message": f"Unknown dashboard: {dashboard}"}])


def _flatten(data: dict[str, Any]) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                rows.append((f"{key}.{sub_key}", sub_value))
        else:
            rows.append((key, value))
    return rows


def render_csv(data: dict[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerows(_flatten(data))
    return buffer.getvalue().encode("utf-8")


def check_dashboard_access(auth: AccessTokenClaims, dashboard: str, *, organization_id: int | None, employer_id: int | None) -> None:
    """Raises if ``auth`` may not read this dashboard with these filters. Institution/hiring/support dashboards
    scoped to one's own organisation are always allowed; anything platform-wide needs that domain's scope."""
    if is_super_admin(auth):
        return
    if dashboard == Dashboard.INSTITUTION:
        if organization_id == auth.organization_id and is_institution_member(auth):
            return
        if can_view_platform(auth):
            return
        raise PermissionDeniedError("You may only see your own institution's dashboard.", code="NOT_YOUR_ORGANIZATION")
    if dashboard == Dashboard.HIRING and employer_id is not None:
        if employer_id == auth.organization_id and is_employer_member(auth):
            return
    if dashboard == Dashboard.HIRING and employer_id is None and organization_id is not None:
        # an institution's own students' hiring outcomes, for that institution's own head and staff
        if organization_id == auth.organization_id and is_institution_member(auth):
            return
    if not can_view_platform(auth, *_DASHBOARD_SCOPE.get(Dashboard(dashboard), ())):
        raise PermissionDeniedError("You do not have permission to view this dashboard.", code="PERMISSION_DENIED")


class ReportService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def get(self, public_id: int) -> ReportDefinition:
        definition = (await self.db.execute(select(ReportDefinition).where(ReportDefinition.public_id == public_id))).scalar_one_or_none()
        if definition is None:
            raise NotFoundError("Report not found.", code="REPORT_NOT_FOUND")
        return definition

    async def get_owned(self, auth: AccessTokenClaims, public_id: int) -> ReportDefinition:
        definition = await self.get(public_id)
        if definition.owner_user_id != auth.user_id and not is_super_admin(auth):
            raise NotFoundError("Report not found.", code="REPORT_NOT_FOUND")
        return definition

    async def create(self, auth: AccessTokenClaims, *, name: str, dashboard: str, filters: dict[str, Any], frequency: str, report_format: str) -> ReportDefinition:
        org, employer = _opt_int(filters.get("organization_id")), _opt_int(filters.get("employer_id"))
        if dashboard == Dashboard.INSTITUTION and org is None:
            raise ValidationFailedError(details=[{"field": "filters.organization_id", "code": "REQUIRED", "message": "The institution dashboard needs an organization_id"}])
        check_dashboard_access(auth, dashboard, organization_id=org, employer_id=employer)
        definition = ReportDefinition(
            public_id=new_public_id(), owner_user_id=auth.user_id, organization_id=org, name=name, dashboard=dashboard, filters=filters, format=report_format,
            frequency=frequency, next_run_at=utcnow() + timedelta(days=_FREQUENCY_DAYS[ReportFrequency(frequency)]),
        )
        self.db.add(definition)
        await self.db.commit()
        return definition

    async def list_mine(self, auth: AccessTokenClaims) -> list[ReportDefinition]:
        return list((await self.db.execute(select(ReportDefinition).where(ReportDefinition.owner_user_id == auth.user_id).order_by(ReportDefinition.created_at.desc()))).scalars())

    async def deactivate(self, definition: ReportDefinition) -> ReportDefinition:
        definition.active = False
        await self.db.commit()
        return definition

    async def runs(self, definition: ReportDefinition) -> list[ReportRun]:
        return list((await self.db.execute(select(ReportRun).where(ReportRun.definition_id == definition.id).order_by(ReportRun.created_at.desc()).limit(self.settings.REPORT_RUN_RETENTION_COUNT))).scalars())

    async def get_run(self, definition: ReportDefinition, run_public_id: int) -> ReportRun:
        run = (await self.db.execute(select(ReportRun).where(ReportRun.definition_id == definition.id, ReportRun.public_id == run_public_id))).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Report run not found.", code="REPORT_RUN_NOT_FOUND")
        return run

    async def run_now(self, definition: ReportDefinition) -> ReportRun:
        """Run a report immediately (an admin asking "show me now"), independent of its schedule."""
        return await _execute(self.db, definition)


async def _execute(db: AsyncSession, definition: ReportDefinition) -> ReportRun:
    since, until = utcnow().date() - timedelta(days=6), utcnow().date()
    run = ReportRun(public_id=new_public_id(), definition_id=definition.id, status=ReportStatus.RUNNING, period_start=since, period_end=until)
    db.add(run)
    await db.flush()
    try:
        data = await run_dashboard(db, definition.dashboard, definition.filters, since=since, until=until)
    except Exception as exc:
        run.status, run.error = ReportStatus.FAILED, str(exc)[:2000]
        await db.commit()
        return run
    content = json.dumps(data, indent=2).encode("utf-8") if definition.format == ReportFormat.JSON else render_csv(data)
    run.status, run.content, run.content_type = ReportStatus.READY, content, ("application/json" if definition.format == ReportFormat.JSON else "text/csv")
    run.dashboard_snapshot, run.row_count, run.generated_at = data, len(_flatten(data)), utcnow()
    write_event(
        db, event_type="report.ready", aggregate_type="report_run", aggregate_id=run.id,
        payload={
            "report_id": str(definition.public_id), "run_id": str(run.public_id), "user_id": str(definition.owner_user_id), "organization_id": str(definition.organization_id) if definition.organization_id else None,
            "name": definition.name, "dashboard": definition.dashboard, "format": definition.format, "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    await db.commit()
    return run


async def run_due_reports(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, *, limit: int = 50) -> int:
    now = utcnow()
    async with sessionmaker() as db:
        due = list((await db.execute(select(ReportDefinition).where(ReportDefinition.active.is_(True), ReportDefinition.next_run_at <= now).limit(limit))).scalars())
    ran = 0
    for definition in due:
        async with sessionmaker() as db:
            locked = (await db.execute(select(ReportDefinition).where(ReportDefinition.id == definition.id).with_for_update())).scalar_one()
            if locked.next_run_at > now:  # another worker already advanced it
                continue
            locked.next_run_at = now + timedelta(days=_FREQUENCY_DAYS[ReportFrequency(locked.frequency)])
            await db.flush()
            await _execute(db, locked)
            ran += 1
    return ran
