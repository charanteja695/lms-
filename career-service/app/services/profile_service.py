"""The skill profile: a student's own (self-declared) items, and the verified items the platform adds from events.

Every change bumps the profile's ``revision`` and emits ``skill_profile.updated`` in the same transaction, so the job portal
(phase 9) can keep a matching index without polling. Verified items are only ever created, updated or deactivated by
``app/services/verified_service.py``; the student-facing methods here refuse to touch them.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import SELF_KINDS, VERIFIED_KINDS, ItemKind, ItemSource
from app.models.profile import Profile, ProfileItem
from app.models.refs import AttemptResult, CourseRef, UserRef
from app.profile_facts import matching_facts
from app.schemas.items import validate_item_data
from app.services.outbox import write_event


@dataclass(slots=True)
class ItemView:
    """An item as a reader sees it: the stored data plus what is derived when it is read (course titles change; percentiles move
    as other students finish)."""

    item: ProfileItem
    data: dict[str, Any]
    derived: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return "Verified" if self.item.verified else "Self-declared"


class ProfileService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ the profile row
    async def get_or_create(self, user_id: int, organization_id: int | None = None) -> Profile:
        profile = (await self.db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
        if profile is None:
            profile = Profile(user_id=user_id, organization_id=organization_id, links=[], target_roles=[], revision=0)
            self.db.add(profile)
            await self.db.flush()
        elif organization_id is not None and profile.organization_id != organization_id:
            profile.organization_id = organization_id
        return profile

    async def get(self, user_id: int) -> Profile | None:
        return (await self.db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()

    async def touch(self, profile: Profile) -> None:
        """Record a change: bump the revision and tell the platform."""
        profile.revision += 1
        await self.db.flush()
        rows = (
            await self.db.execute(
                select(ProfileItem.kind, func.count()).where(ProfileItem.user_id == profile.user_id, ProfileItem.active.is_(True)).group_by(ProfileItem.kind)
            )
        ).all()
        counts: dict[str, int] = {str(kind): int(n) for kind, n in rows}
        items = list((await self.db.execute(select(ProfileItem).where(ProfileItem.user_id == profile.user_id, ProfileItem.active.is_(True)))).scalars())
        write_event(
            self.db, event_type="skill_profile.updated", aggregate_type="profile", aggregate_id=profile.id,
            payload={
                "user_id": str(profile.user_id), "organization_id": str(profile.organization_id) if profile.organization_id else None, "revision": profile.revision,
                "headline": profile.headline, "target_roles": list(profile.target_roles or []),
                "verified": {kind.value: int(counts.get(kind.value, 0)) for kind in VERIFIED_KINDS},
                "self_declared": {kind.value: int(counts.get(kind.value, 0)) for kind in SELF_KINDS}, "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "facts": matching_facts(profile, items),
            },
        )

    async def update_profile(
        self, user_id: int, organization_id: int | None, *, fields: dict[str, Any]
    ) -> Profile:
        profile = await self.get_or_create(user_id, organization_id)
        for name, value in fields.items():
            setattr(profile, name, value)
        await self.touch(profile)
        await self.db.commit()
        return profile

    # ------------------------------------------------------------------ self-declared items
    async def _count(self, user_id: int, kind: ItemKind) -> int:
        return int((await self.db.execute(select(func.count()).select_from(ProfileItem).where(ProfileItem.user_id == user_id, ProfileItem.kind == kind))).scalar_one())

    async def add_item(self, user_id: int, organization_id: int | None, kind: ItemKind, data: dict[str, Any]) -> ProfileItem:
        if kind not in SELF_KINDS:
            raise PermissionDeniedError("Certificates, courses and scores come from the platform and cannot be added by hand.", code="VERIFIED_KIND")
        clean = validate_item_data(kind, data)
        if await self._count(user_id, kind) >= self.settings.MAX_PROFILE_ITEMS_PER_KIND:
            raise ConflictError(f"You can keep at most {self.settings.MAX_PROFILE_ITEMS_PER_KIND} {kind.value} entries.", code="TOO_MANY_ITEMS")
        profile = await self.get_or_create(user_id, organization_id)
        last = (await self.db.execute(select(func.max(ProfileItem.position)).where(ProfileItem.user_id == user_id, ProfileItem.kind == kind))).scalar_one()
        item = ProfileItem(
            public_id=new_public_id(), user_id=user_id, kind=kind, verified=False, source=ItemSource.SELF, data=clean, position=(last if last is not None else -1) + 1, active=True
        )
        self.db.add(item)
        await self.touch(profile)
        await self.db.commit()
        return item

    async def add_items(self, user_id: int, organization_id: int | None, entries: list[tuple[ItemKind, dict[str, Any]]]) -> list[ProfileItem]:
        """Add several entries at once (an imported resume): all are validated first, and either all are saved or none."""
        problems: list[dict[str, Any]] = []
        clean: list[tuple[ItemKind, dict[str, Any]]] = []
        for index, (kind, data) in enumerate(entries):
            if kind not in SELF_KINDS:
                problems.append({"field": f"items.{index}.kind", "code": "VERIFIED_KIND", "message": "Certificates, courses and scores come from the platform"})
                continue
            try:
                clean.append((kind, validate_item_data(kind, data)))
            except ValidationFailedError as exc:
                problems.extend({**d, "field": f"items.{index}.{d.get('field', 'data')}"} for d in (exc.details or []))
        if problems:
            raise ValidationFailedError(details=problems)
        for kind in {k for k, _ in clean}:
            if await self._count(user_id, kind) + sum(1 for k, _ in clean if k == kind) > self.settings.MAX_PROFILE_ITEMS_PER_KIND:
                raise ConflictError(f"You can keep at most {self.settings.MAX_PROFILE_ITEMS_PER_KIND} {kind.value} entries.", code="TOO_MANY_ITEMS")
        profile = await self.get_or_create(user_id, organization_id)
        positions: dict[ItemKind, int] = {}
        items: list[ProfileItem] = []
        for kind, data in clean:
            if kind not in positions:
                last = (await self.db.execute(select(func.max(ProfileItem.position)).where(ProfileItem.user_id == user_id, ProfileItem.kind == kind))).scalar_one()
                positions[kind] = last if last is not None else -1
            positions[kind] += 1
            item = ProfileItem(public_id=new_public_id(), user_id=user_id, kind=kind, verified=False, source=ItemSource.SELF, data=data, position=positions[kind], active=True)
            self.db.add(item)
            items.append(item)
        await self.touch(profile)
        await self.db.commit()
        return items

    async def get_item(self, user_id: int, public_id: int) -> ProfileItem:
        item = (await self.db.execute(select(ProfileItem).where(ProfileItem.public_id == public_id, ProfileItem.user_id == user_id))).scalar_one_or_none()
        if item is None:
            raise NotFoundError("Profile item not found.", code="ITEM_NOT_FOUND")
        return item

    @staticmethod
    def _require_editable(item: ProfileItem) -> None:
        if item.verified:
            raise PermissionDeniedError("Verified items come from the platform and cannot be changed.", code="VERIFIED_ITEM_READONLY")

    async def update_item(self, item: ProfileItem, data: dict[str, Any]) -> ProfileItem:
        self._require_editable(item)
        item.data = validate_item_data(ItemKind(item.kind), data)
        profile = await self.get_or_create(item.user_id)
        await self.touch(profile)
        await self.db.commit()
        return item

    async def delete_item(self, item: ProfileItem) -> None:
        self._require_editable(item)
        profile = await self.get_or_create(item.user_id)
        await self.db.delete(item)
        await self.touch(profile)
        await self.db.commit()

    async def reorder(self, user_id: int, kind: ItemKind, ordered_ids: list[int]) -> None:
        items = list((await self.db.execute(select(ProfileItem).where(ProfileItem.user_id == user_id, ProfileItem.kind == kind))).scalars())
        by_id = {i.public_id: i for i in items}
        if len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != set(by_id):
            raise ConflictError("Send every item of this kind exactly once.", code="INVALID_ORDER")
        for position, public_id in enumerate(ordered_ids):
            by_id[public_id].position = position
        await self.touch(await self.get_or_create(user_id))
        await self.db.commit()

    # ------------------------------------------------------------------ reading
    async def _percentile(self, course_id: int, best: float) -> tuple[int | None, int]:
        """(percentile, cohort size). ``None`` below ``PERCENTILE_MIN_COHORT``: a percentile among a handful of students is
        noise, and could identify a person."""
        bests = (
            select(AttemptResult.user_id, func.max(AttemptResult.percent).label("best"))
            .where(AttemptResult.course_id == course_id, AttemptResult.result == "passed", AttemptResult.percent.is_not(None))
            .group_by(AttemptResult.user_id)
            .subquery()
        )
        below_expr = func.sum(case((bests.c.best < best, 1), else_=0))
        equal_expr = func.sum(case((bests.c.best == best, 1), else_=0))
        total, lower, same = (await self.db.execute(select(func.count(), below_expr, equal_expr).select_from(bests))).one()
        total = int(total or 0)
        if total < self.settings.PERCENTILE_MIN_COHORT:
            return None, total
        return round(100 * (int(lower or 0) + 0.5 * int(same or 0)) / total), total

    async def views(self, user_id: int, *, kinds: tuple[ItemKind, ...] | None = None, include_inactive: bool = False) -> list[ItemView]:
        stmt = select(ProfileItem).where(ProfileItem.user_id == user_id).order_by(ProfileItem.kind, ProfileItem.position, ProfileItem.created_at)
        if kinds:
            stmt = stmt.where(ProfileItem.kind.in_([k.value for k in kinds]))
        if not include_inactive:
            stmt = stmt.where(ProfileItem.active.is_(True))
        items = list((await self.db.execute(stmt)).scalars())
        course_ids = {int(i.data["course_id"]) for i in items if i.data.get("course_id")}
        titles = {c.course_id: c.title for c in (await self.db.execute(select(CourseRef).where(CourseRef.course_id.in_(course_ids)))).scalars()} if course_ids else {}
        views: list[ItemView] = []
        for item in items:
            data = dict(item.data)
            derived: dict[str, Any] = {}
            if data.get("course_id"):
                derived["course_title"] = titles.get(int(data["course_id"])) or "Course"
            if item.kind == ItemKind.SKILL_SCORE and item.active and data.get("best_percent") is not None:
                derived["percentile"], derived["cohort_size"] = await self._percentile(int(data["course_id"]), float(data["best_percent"]))
            views.append(ItemView(item=item, data=data, derived=derived))
        return views

    async def user_ref(self, user_id: int) -> UserRef | None:
        return await self.db.get(UserRef, user_id)
