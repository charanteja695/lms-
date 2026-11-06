"""Reports follow user-management's permission-matrix cells: seeing a dashboard and scheduling its report are separate."""

from dataclasses import replace

import pytest

from app.core.exceptions import PermissionDeniedError
from app.services.report_service import check_dashboard_access
from tests.conftest import make_claims

ORG = 1755000000090901


def test_a_staff_member_left_view_only_sees_the_dashboard_but_schedules_no_report() -> None:
    viewer = replace(make_claims(user_id=1, role="staff", organization_id=ORG, scopes=("reports.view", "analytics.own"), defaults=False), organization_type="institution")
    check_dashboard_access(viewer, "institution", organization_id=ORG, employer_id=None)
    with pytest.raises(PermissionDeniedError):
        check_dashboard_access(viewer, "institution", organization_id=ORG, employer_id=None, action="export")
