"""Permissions become a page × action matrix: turn stored feature-key overrides into cell overrides.

Institution heads, staff and students now hold cells (``batches.create``); each cell implies the older feature key the
other services check. A stored grant or removal of a feature key becomes the same grant or removal of every cell that
implies it (a grant also grants that page's View, without which the page's other actions do not count). Company roles
keep their feature-key rows; admins had none (their scopes live on the user).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20 09:00:00
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of app/permissions/pages.py at this revision: feature key -> the cells implying it, and who may hold
# each page.
_CELLS: dict[str, tuple[str, ...]] = {
    "academics.manage": ("academic_structure.create", "academic_structure.update", "academic_structure.delete"),
    "academics.view": ("academic_structure.view",),
    "ai.usage.own": ("ai_usage.view",),
    "analytics.own": ("reports.view", "reports.export"),
    "assessments.grade": ("attempts.view", "attempts.update"),
    "assessments.take": ("my_tests.view",),
    "billing.contact": ("billing.view", "billing.update"),
    "career.profile": ("my_career.view", "my_career.create", "my_career.update", "my_career.delete"),
    "career.students": ("student_profiles.view",),
    "catalog.browse": ("courses.view",),
    "catalog.read": ("my_learning.view", "courses.view"),
    "certificates.own": ("my_certificates.view", "my_certificates.export"),
    "certificates.students": ("certificates.view", "certificates.export"),
    "code.practice": ("coding_practice.view",),
    "code.submissions": ("my_submissions.view",),
    "interviews.practice": ("ai_interview.view", "ai_interview.create"),
    "jobs.apply": ("jobs.view", "jobs.create", "jobs.revoke"),
    "jobs.drives.propose": ("placements.create",),
    "jobs.placements": ("placements.view",),
    "learning.batches.manage": ("batches.create", "batches.revoke"),
    "learning.batches.view": ("batches.view",),
    "learning.study": ("my_learning.view",),
    "proctoring.monitor": ("proctoring.view", "proctoring.update"),
    "proctoring.take": ("exam_reviews.view", "exam_reviews.create"),
    "subscriptions.request": ("course_requests.view", "course_requests.create"),
    "support.agent": ("support_queue.view", "support_queue.update"),
    "support.ask": ("support.view", "support.create"),
    "support.assign": ("support_queue.approve",),
    "tutor.chat": ("ai_tutor.view",),
    "tutor.conversations.view": ("tutor_chats.view",),
    "tutor.faq.manage": ("tutor_faq.view", "tutor_faq.create", "tutor_faq.update", "tutor_faq.delete"),
}
_H, _S, _L = "institution_head", "staff", "student"
_HOLDERS: dict[str, tuple[str, ...]] = {
    "academic_structure": (_H, _S),
    "ai_interview": (_L,),
    "ai_tutor": (_L,),
    "ai_usage": (_H, _S),
    "attempts": (_H, _S),
    "batches": (_H, _S),
    "billing": (_H,),
    "certificates": (_H, _S),
    "coding_practice": (_H, _S, _L),
    "course_requests": (_H,),
    "courses": (_H, _S),
    "exam_reviews": (_L,),
    "jobs": (_L,),
    "my_career": (_L,),
    "my_certificates": (_L,),
    "my_learning": (_L,),
    "my_submissions": (_L,),
    "my_tests": (_L,),
    "placements": (_H, _S),
    "proctoring": (_H, _S),
    "reports": (_H, _S),
    "student_profiles": (_H, _S),
    "support": (_L,),
    "support_queue": (_H, _S),
    "tutor_chats": (_H, _S),
    "tutor_faq": (_H, _S),
}
_MATRIX_ROLES = (_H, _S, _L)


def _cells(feature: str, role: str, allowed: bool) -> set[str]:
    out: set[str] = set()
    for cell in _CELLS.get(feature, ()):
        page = cell.rpartition(".")[0]
        if role in _HOLDERS.get(page, ()):
            out.add(cell)
            if allowed:
                out.add(f"{page}.view")
    return out


def upgrade() -> None:
    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            "SELECT id, role, permission, allowed, changed_by FROM role_permissions WHERE role IN :roles"
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {"roles": list(_MATRIX_ROLES)},
    ).fetchall()
    for row_id, role, feature, allowed, changed_by in rows:
        if feature not in _CELLS:
            continue
        for cell in _cells(feature, role, allowed):
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (id, role, permission, allowed, changed_by) "
                    "VALUES (:id, :role, :cell, :allowed, :by) ON CONFLICT (role, permission) DO NOTHING"
                ),
                {"id": uuid.uuid4(), "role": role, "cell": cell, "allowed": allowed, "by": changed_by},
            )
        connection.execute(sa.text("DELETE FROM role_permissions WHERE id = :id"), {"id": row_id})

    rows = connection.execute(
        sa.text(
            "SELECT p.id, p.user_id, u.role, p.permission, p.allowed, p.reason, p.changed_by "
            "FROM user_permissions p JOIN users u ON u.id = p.user_id WHERE u.role IN :roles"
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {"roles": list(_MATRIX_ROLES)},
    ).fetchall()
    touched: set[object] = set()
    for row_id, user_id, role, feature, allowed, reason, changed_by in rows:
        if feature not in _CELLS:
            continue
        for cell in _cells(feature, role, allowed):
            connection.execute(
                sa.text(
                    "INSERT INTO user_permissions (id, user_id, permission, allowed, reason, changed_by) "
                    "VALUES (:id, :user_id, :cell, :allowed, :reason, :by) ON CONFLICT (user_id, permission) DO NOTHING"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id,
                    "cell": cell,
                    "allowed": allowed,
                    "reason": reason,
                    "by": changed_by,
                },
            )
        connection.execute(sa.text("DELETE FROM user_permissions WHERE id = :id"), {"id": row_id})
        touched.add(user_id)
    for user_id in touched:  # their next token carries the cells
        connection.execute(
            sa.text("UPDATE users SET token_version = token_version + 1 WHERE id = :id"), {"id": user_id}
        )


def downgrade() -> None:
    """Cell overrides are not turned back into feature keys: the super admin re-applies them if this is rolled back."""
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role IN ('institution_head', 'staff', 'student', 'admin') AND permission NOT IN :keys"
        )
        .bindparams(sa.bindparam("keys", expanding=True))
        .params(keys=list(_CELLS))
    )
