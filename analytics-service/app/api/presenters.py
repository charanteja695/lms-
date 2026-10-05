from app.models.report import ReportDefinition, ReportRun
from app.schemas.report import ReportOut, ReportRunOut


def report_out(definition: ReportDefinition) -> ReportOut:
    return ReportOut(
        report_id=definition.public_id, name=definition.name, dashboard=definition.dashboard, filters=definition.filters, format=definition.format,
        frequency=definition.frequency, next_run_at=definition.next_run_at, active=definition.active, created_at=definition.created_at,
    )


def report_run_out(run: ReportRun) -> ReportRunOut:
    return ReportRunOut(
        run_id=run.public_id, status=run.status, period_start=run.period_start.isoformat() if run.period_start else None, period_end=run.period_end.isoformat() if run.period_end else None,
        row_count=run.row_count, content_type=run.content_type, error=run.error, dashboard_snapshot=run.dashboard_snapshot, generated_at=run.generated_at, created_at=run.created_at,
    )
