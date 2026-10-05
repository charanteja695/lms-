"""Certificate templates: authored as drafts, activated by a reviewer. At most one template is active per course (and
one platform default); activating a template archives the one it replaces. Certificates snapshot the template they are
issued with, so none of this ever changes a certificate already issued."""

import uuid
from typing import Any

from lms_common.pagination import paginate
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import TemplateStatus
from app.models.template import CertificateTemplate
from app.render.layout import (
    DEFAULT_GRADE_BANDS,
    DEFAULT_TEMPLATE,
    validate_bands,
    validate_color,
    validate_text_placeholders,
)
from app.schemas.template import TemplateCreate, TemplateUpdate


def snapshot_of(template: CertificateTemplate) -> dict[str, Any]:
    return {
        "name": template.name,
        "title_text": template.title_text,
        "body_text": template.body_text,
        "footer_text": template.footer_text,
        "accent_color": template.accent_color,
        "signatories": template.signatories,
        "grade_bands": template.grade_bands,
    }


class TemplateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, public_id: int) -> CertificateTemplate:
        template = (await self.db.execute(select(CertificateTemplate).where(CertificateTemplate.public_id == public_id))).scalar_one_or_none()
        if template is None:
            raise NotFoundError("Template not found.", code="TEMPLATE_NOT_FOUND")
        return template

    async def list_templates(
        self, *, course_id: int | None, status: str | None, page: int, per_page: int
    ) -> tuple[list[CertificateTemplate], int, bool]:
        stmt = select(CertificateTemplate)
        if course_id is not None:
            stmt = stmt.where(CertificateTemplate.course_id == course_id)
        if status:
            stmt = stmt.where(CertificateTemplate.status == status)
        rows, total, exact = await paginate(self.db, stmt.order_by(CertificateTemplate.created_at.desc(), CertificateTemplate.id), page, per_page)
        return rows, total, exact

    @staticmethod
    def _validated(fields: dict[str, Any]) -> dict[str, Any]:
        if fields.get("body_text"):
            validate_text_placeholders("body_text", fields["body_text"])
        if fields.get("footer_text"):
            validate_text_placeholders("footer_text", fields["footer_text"])
        if fields.get("accent_color"):
            fields["accent_color"] = validate_color(fields["accent_color"])
        if fields.get("grade_bands") is not None:
            fields["grade_bands"] = validate_bands(fields["grade_bands"])
        if fields.get("signatories") is not None:
            fields["signatories"] = [{"name": s["name"], "title": s.get("title", "")} for s in fields["signatories"]]
        return fields

    async def create(self, data: TemplateCreate, auth: AccessTokenClaims) -> CertificateTemplate:
        fields = self._validated(data.model_dump(mode="json"))
        template = CertificateTemplate(
            public_id=new_public_id(),
            course_id=fields["course_id"] and int(fields["course_id"]),
            name=fields["name"],
            title_text=fields["title_text"],
            body_text=fields["body_text"] or DEFAULT_TEMPLATE["body_text"],
            footer_text=fields["footer_text"] if fields["footer_text"] is not None else DEFAULT_TEMPLATE["footer_text"],
            accent_color=fields["accent_color"],
            signatories=fields["signatories"],
            grade_bands=fields["grade_bands"] or DEFAULT_GRADE_BANDS,
            created_by=auth.user_id,
        )
        self.db.add(template)
        await self.db.commit()
        return template

    async def update(self, template: CertificateTemplate, data: TemplateUpdate) -> CertificateTemplate:
        if template.status != TemplateStatus.DRAFT:
            raise ConflictError("Only a draft template can be edited; create a new draft to change an active one.", code="TEMPLATE_NOT_DRAFT")
        fields = self._validated(data.model_dump(mode="json", exclude_unset=True))
        for name, value in fields.items():
            if value is not None or name == "footer_text":
                setattr(template, name, value)
        await self.db.commit()
        return template

    async def activate(self, template: CertificateTemplate) -> CertificateTemplate:
        if template.status == TemplateStatus.ARCHIVED:
            raise ConflictError("An archived template cannot be activated; copy it into a new draft.", code="TEMPLATE_ARCHIVED")
        if template.status == TemplateStatus.ACTIVE:
            return template
        same_scope = CertificateTemplate.course_id.is_(None) if template.course_id is None else CertificateTemplate.course_id == template.course_id
        await self.db.execute(
            update(CertificateTemplate)
            .where(same_scope, CertificateTemplate.status == TemplateStatus.ACTIVE)
            .values(status=TemplateStatus.ARCHIVED)
        )
        template.status, template.activated_at = TemplateStatus.ACTIVE, utcnow()
        await self.db.commit()
        return template

    async def archive(self, template: CertificateTemplate) -> CertificateTemplate:
        template.status = TemplateStatus.ARCHIVED
        await self.db.commit()
        return template

    async def resolve(self, course_id: int) -> tuple[uuid.UUID | None, dict[str, Any]]:
        """The template a new certificate for ``course_id`` uses: the course's own, else the platform default, else the
        built-in one. Returns its id (None for the built-in) and a snapshot."""
        for scope in (CertificateTemplate.course_id == course_id, CertificateTemplate.course_id.is_(None)):
            template = (
                await self.db.execute(
                    select(CertificateTemplate)
                    .where(scope, CertificateTemplate.status == TemplateStatus.ACTIVE)
                    .order_by(CertificateTemplate.activated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if template is not None:
                return template.id, snapshot_of(template)
        return None, dict(DEFAULT_TEMPLATE)
