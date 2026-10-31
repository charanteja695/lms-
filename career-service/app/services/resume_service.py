"""Resumes: the draft a student edits, frozen versions of it, and the public share link.

A resume is one document for one target role (a student keeps several: "multiple resume versions per target role"); inside a
resume, *versions* are snapshots — the draft as it was plus the document it resolved to — that can be restored, exported and
shared. Sharing pins a link to one version, so editing the draft never changes what an already-sent link shows.
"""

import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ats.scoring import AtsReport, score_document
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import DEFAULT_TITLES, SECTION_KINDS, ExperienceLevel, SectionKey, VersionSource
from app.models.resume import Resume, ResumeTemplate, ResumeVersion
from app.rendering.templates import DEFAULT_TEMPLATE_KEY, DEFAULT_TEMPLATES
from app.resume.document import build_document, default_draft, reorder_sections
from app.services.outbox import write_event
from app.services.profile_service import ItemView, ProfileService

_BULLET_KINDS = {"experience", "education", "project"}


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class ResumeService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.profiles = ProfileService(db, settings)

    # ------------------------------------------------------------------ templates
    async def ensure_templates(self) -> None:
        """Make sure the built-in templates exist (idempotent; safe when two processes start together)."""
        existing = set((await self.db.execute(select(ResumeTemplate.key))).scalars())
        added = False
        for key, spec in DEFAULT_TEMPLATES.items():
            if key not in existing:
                self.db.add(ResumeTemplate(key=key, name=spec["name"], description=spec["description"], config=spec["config"], ats_safe=True, active=True))
                added = True
        if added:
            try:
                await self.db.commit()
            except IntegrityError:
                await self.db.rollback()

    async def templates(self) -> list[ResumeTemplate]:
        await self.ensure_templates()
        return list((await self.db.execute(select(ResumeTemplate).where(ResumeTemplate.active.is_(True)).order_by(ResumeTemplate.key))).scalars())

    async def template(self, key: str) -> ResumeTemplate:
        row = (await self.db.execute(select(ResumeTemplate).where(ResumeTemplate.key == key, ResumeTemplate.active.is_(True)))).scalar_one_or_none()
        if row is None:
            await self.ensure_templates()
            row = (await self.db.execute(select(ResumeTemplate).where(ResumeTemplate.key == key, ResumeTemplate.active.is_(True)))).scalar_one_or_none()
        if row is None:
            raise ValidationFailedError(details=[{"field": "template_key", "code": "UNKNOWN_TEMPLATE", "message": "No such template"}])
        return row

    # ------------------------------------------------------------------ lookup
    async def get(self, user_id: int | str, public_id: int | str) -> Resume:
        u_id = int(str(user_id))
        p_id = int(str(public_id))
        resume = (await self.db.execute(select(Resume).where(Resume.public_id == p_id, Resume.user_id == u_id, Resume.deleted_at.is_(None)))).scalar_one_or_none()
        if resume is None:
            raise NotFoundError("Resume not found.", code="RESUME_NOT_FOUND")
        return resume

    async def list_for(self, user_id: int, *, page: int, per_page: int) -> tuple[list[Resume], int]:
        base = select(Resume).where(Resume.user_id == user_id, Resume.deleted_at.is_(None))
        total = int((await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
        rows = (await self.db.execute(base.order_by(Resume.updated_at.desc(), Resume.id).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    # ------------------------------------------------------------------ create / edit
    async def create(
        self, user_id: int, organization_id: int | None, *, title: str, target_role: str | None, template_key: str | None, job_description: str | None, blank: bool,
        experience_level: ExperienceLevel = ExperienceLevel.FRESHER,
    ) -> Resume:
        count = int((await self.db.execute(select(func.count()).select_from(Resume).where(Resume.user_id == user_id, Resume.deleted_at.is_(None)))).scalar_one())
        if count >= self.settings.MAX_RESUMES_PER_USER:
            raise ConflictError(f"You can keep at most {self.settings.MAX_RESUMES_PER_USER} resumes. Delete one first.", code="TOO_MANY_RESUMES")
        template = await self.template(template_key or DEFAULT_TEMPLATE_KEY)
        views = [] if blank else await self.profiles.views(user_id)
        draft = default_draft(views, experience_level)
        resume = Resume(
            public_id=new_public_id(), user_id=user_id, organization_id=organization_id, title=title, target_role=target_role, template_key=template.key,
            experience_level=experience_level.value, job_description=job_description, draft=draft, draft_revision=0, latest_version_no=0, share_show_contact=False,
            share_views=0,
        )
        self.db.add(resume)
        await self.db.commit()
        return resume

    async def _validated_draft(self, user_id: int, draft: dict[str, Any]) -> dict[str, Any]:
        """Every referenced item must be the student's own, active, and filed under the section its kind belongs to; a custom
        bullet wording is accepted only on self-declared items."""
        views: dict[str, ItemView] = {str(v.item.public_id): v for v in await self.profiles.views(user_id)}
        problems: list[dict[str, str]] = []
        sections = []
        for s_index, section in enumerate(draft["sections"]):
            key = SectionKey(section["key"])
            seen: set[str] = set()
            items = []
            for i_index, ref in enumerate(section["items"]):
                item_id = str(ref["item_id"])
                where = f"draft.sections.{s_index}.items.{i_index}"
                view = views.get(item_id)
                if view is None:
                    problems.append({"field": f"{where}.item_id", "code": "UNKNOWN_ITEM", "message": "Not one of your active profile items"})
                elif view.item.kind != SECTION_KINDS[key].value:
                    problems.append({"field": f"{where}.item_id", "code": "WRONG_SECTION", "message": f"A {view.item.kind} does not belong in {key.value}"})
                elif item_id in seen:
                    problems.append({"field": f"{where}.item_id", "code": "DUPLICATE_ITEM", "message": "Listed twice in one section"})
                elif ref.get("bullets") is not None and (view.item.verified or view.item.kind not in _BULLET_KINDS):
                    problems.append({"field": f"{where}.bullets", "code": "VERIFIED_ITEM_READONLY", "message": "Only your own entries can be reworded"})
                seen.add(item_id)
                items.append({"item_id": item_id, "bullets": ref.get("bullets")})
            sections.append({"key": key.value, "title": section.get("title") or DEFAULT_TITLES[key], "visible": section.get("visible", True), "items": items})
        if problems:
            raise ValidationFailedError(details=problems)
        return {"summary": draft["summary"], "personal": draft["personal"], "sections": sections}

    async def update(
        self, resume: Resume, *, expected_revision: int, title: str | None, target_role: str | None, template_key: str | None, job_description: str | None, draft: dict[str, Any] | None,
        experience_level: ExperienceLevel | None = None,
    ) -> Resume:
        locked = (await self.db.execute(select(Resume).where(Resume.id == resume.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if locked.draft_revision != expected_revision:
            raise ConflictError("This resume was changed somewhere else. Reload it and apply your change again.", code="STALE_DRAFT")
        if title is not None:
            locked.title = title
        if target_role is not None:
            locked.target_role = target_role
        if template_key is not None:
            locked.template_key = (await self.template(template_key)).key
        if job_description is not None:
            locked.job_description = job_description or None
        if draft is not None:
            locked.draft = await self._validated_draft(locked.user_id, draft)
        if experience_level is not None and experience_level.value != locked.experience_level:
            locked.experience_level = experience_level.value
            if draft is None:  # an explicit draft keeps the order the student chose
                locked.draft = reorder_sections(locked.draft, experience_level)
        locked.draft_revision += 1
        await self.db.commit()
        return locked

    async def duplicate(self, resume: Resume, *, title: str) -> Resume:
        count = int((await self.db.execute(select(func.count()).select_from(Resume).where(Resume.user_id == resume.user_id, Resume.deleted_at.is_(None)))).scalar_one())
        if count >= self.settings.MAX_RESUMES_PER_USER:
            raise ConflictError(f"You can keep at most {self.settings.MAX_RESUMES_PER_USER} resumes. Delete one first.", code="TOO_MANY_RESUMES")
        copy = Resume(
            public_id=new_public_id(), user_id=resume.user_id, organization_id=resume.organization_id, title=title, target_role=resume.target_role,
            template_key=resume.template_key, experience_level=resume.experience_level, job_description=resume.job_description, draft=resume.draft, draft_revision=0, latest_version_no=0, share_show_contact=False, share_views=0,
        )
        self.db.add(copy)
        await self.db.commit()
        return copy

    async def delete(self, resume: Resume) -> None:
        resume.deleted_at = utcnow()
        resume.share_token = None  # a deleted resume's public link stops working at once
        write_event(self.db, event_type="resume.updated", aggregate_type="resume", aggregate_id=resume.id, payload=self._event(resume, "deleted", None))
        await self.db.commit()

    # ------------------------------------------------------------------ the document
    async def document(self, resume: Resume, *, draft: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        """Resolve a draft (the resume's own by default) against the profile as it is now. Also returns the raw data of each item,
        which the JSON Resume export reads its dates from."""
        user_id = resume.user_id
        profile = await self.profiles.get(user_id)
        ref = await self.profiles.user_ref(user_id)
        views = await self.profiles.views(user_id)
        name = " ".join(x for x in ((ref.first_name if ref else ""), (ref.last_name if ref else "")) if x) or "Student"
        document = build_document(
            draft or resume.draft, name=name, email=ref.email if ref else None, phone=profile.phone if profile else None, location=profile.location if profile else None,
            headline=profile.headline if profile else None, links=list(profile.links or []) if profile else [], profile_summary=profile.summary if profile else None, views=views,
        )
        return document, {str(v.item.public_id): v.data for v in views}

    async def ats(self, resume: Resume, *, job_description: str | None, document: dict[str, Any] | None = None) -> AtsReport:
        template = await self.template(resume.template_key)
        doc = document or (await self.document(resume))[0]
        return score_document(
            doc, template_ats_safe=template.ats_safe, job_description=job_description if job_description is not None else resume.job_description,
            experience_level=ExperienceLevel(resume.experience_level),
        )

    # ------------------------------------------------------------------ versions
    def _event(self, resume: Resume, action: str, version_no: int | None) -> dict[str, Any]:
        return {
            "resume_id": str(resume.public_id), "user_id": str(resume.user_id), "organization_id": str(resume.organization_id) if resume.organization_id else None,
            "action": action, "version_no": version_no, "target_role": resume.target_role, "occurred_at": _iso(utcnow()),
        }

    async def create_version(self, resume: Resume, *, label: str | None, note: str | None, source: VersionSource = VersionSource.MANUAL) -> ResumeVersion:
        locked = (await self.db.execute(select(Resume).where(Resume.id == resume.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        document, _ = await self.document(locked)
        report = await self.ats(locked, job_description=None, document=document)
        locked.latest_version_no += 1
        version = ResumeVersion(
            public_id=new_public_id(), resume_id=locked.id, version_no=locked.latest_version_no, label=label, source=source, template_key=locked.template_key,
            draft=locked.draft, document=document, ats_score=report.score, note=note,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune(locked)
        write_event(self.db, event_type="resume.updated", aggregate_type="resume", aggregate_id=locked.id, payload={**self._event(locked, "version_saved", version.version_no), "ats_score": report.score})
        await self.db.commit()
        return version

    async def _prune(self, resume: Resume) -> None:
        """Keep the newest ``MAX_VERSIONS_PER_RESUME``; a version a live share link points at is never pruned."""
        rows = list((await self.db.execute(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id).order_by(ResumeVersion.version_no.desc()))).scalars())
        for old in rows[self.settings.MAX_VERSIONS_PER_RESUME :]:
            if resume.share_token and old.version_no == resume.share_version_no:
                continue
            await self.db.delete(old)

    async def versions(self, resume: Resume) -> list[ResumeVersion]:
        return list((await self.db.execute(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id).order_by(ResumeVersion.version_no.desc()))).scalars())

    async def version(self, resume: Resume, version_no: int) -> ResumeVersion:
        row = (await self.db.execute(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id, ResumeVersion.version_no == version_no))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Version not found.", code="VERSION_NOT_FOUND")
        return row

    async def restore(self, resume: Resume, version_no: int) -> Resume:
        old = await self.version(resume, version_no)
        await self.create_version(resume, label=f"Before restoring v{version_no}", note=None, source=VersionSource.RESTORE)  # nothing is lost by restoring
        locked = (await self.db.execute(select(Resume).where(Resume.id == resume.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        locked.draft, locked.template_key = old.draft, old.template_key
        locked.draft_revision += 1
        write_event(self.db, event_type="resume.updated", aggregate_type="resume", aggregate_id=locked.id, payload=self._event(locked, "restored", version_no))
        await self.db.commit()
        return locked

    # ------------------------------------------------------------------ sharing
    async def share(self, resume: Resume, *, version_no: int | None, expires_in_days: int | None, show_contact: bool) -> Resume:
        if version_no is None:
            version_no = (await self.create_version(resume, label="Shared", note=None)).version_no
        else:
            await self.version(resume, version_no)
        locked = (await self.db.execute(select(Resume).where(Resume.id == resume.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        locked.share_token = secrets.token_urlsafe(24)  # a new link every time: sharing again replaces (and kills) the old one
        locked.share_version_no = version_no
        locked.share_show_contact = show_contact
        locked.share_expires_at = utcnow() + timedelta(days=expires_in_days or self.settings.SHARE_DEFAULT_DAYS)
        locked.share_views = 0
        write_event(self.db, event_type="resume.updated", aggregate_type="resume", aggregate_id=locked.id, payload=self._event(locked, "shared", version_no))
        await self.db.commit()
        return locked

    async def unshare(self, resume: Resume) -> None:
        if resume.share_token:
            resume.share_token, resume.share_expires_at, resume.share_version_no = None, None, None
            write_event(self.db, event_type="resume.updated", aggregate_type="resume", aggregate_id=resume.id, payload=self._event(resume, "unshared", None))
            await self.db.commit()

    async def public(self, token: str) -> tuple[Resume, ResumeVersion]:
        """The version a live share link points at. An unknown, revoked, expired or deleted link is one and the same 404."""
        resume = (await self.db.execute(select(Resume).where(Resume.share_token == token, Resume.deleted_at.is_(None)))).scalar_one_or_none()
        if resume is None or resume.share_version_no is None or (resume.share_expires_at and resume.share_expires_at < utcnow()):
            raise NotFoundError("This link is not available.", code="SHARE_NOT_FOUND")
        version = await self.version(resume, resume.share_version_no)
        resume.share_views += 1
        await self.db.commit()
        return resume, version

    @staticmethod
    def public_document(document: dict[str, Any], *, show_contact: bool) -> dict[str, Any]:
        """A public page never shows contact details unless the student chose to; the verified name stays."""
        if show_contact:
            return document
        personal = {**document["personal"], "email": None, "phone": None, "location": None, "links": []}
        return {**document, "personal": personal}

