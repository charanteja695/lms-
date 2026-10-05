from lms_common.pagination import paginate
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.entitlement_cache import get_entitlement
from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.models.batch import Batch
from app.schemas.batch import BatchCreate
from app.schemas.common import ListQuery
from app.services.course_structure_service import CourseStructureService
from app.services.institution_ref_service import InstitutionRefService


class BatchService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis

    async def create(self, actor_user_id: int, organization_id: int, data: BatchCreate) -> Batch:
        await InstitutionRefService(self.db).get_active(organization_id)
        version = await CourseStructureService(self.db).get_latest_published_for_course(data.course_id)

        entitlement = await get_entitlement(
            self.redis, key_prefix=self.settings.ENTITLEMENT_KEY_PREFIX, organization_id=organization_id, course_id=data.course_id
        )
        if entitlement is None:
            raise BadRequestError(
                "This institution has no active subscription to this course.", code="NO_ACTIVE_SUBSCRIPTION"
            )

        batch = Batch(
            public_id=new_public_id(),
            organization_id=organization_id,
            version_id=version.version_id,
            subscription_id=entitlement.subscription_id,
            name=data.name,
            created_by=actor_user_id,
        )
        self.db.add(batch)
        await commit_or_conflict(self.db)
        batch.course_version = version  # already loaded above; avoids a lazy-load for BatchOut.course_id/title
        return batch

    async def get(self, batch_id: int) -> Batch:
        batch = (
            await self.db.execute(select(Batch).where(Batch.public_id == batch_id).options(selectinload(Batch.course_version)))
        ).scalar_one_or_none()
        if batch is None:
            raise NotFoundError("Batch not found.", code="BATCH_NOT_FOUND")
        return batch

    async def list_batches(self, query: ListQuery, *, organization_id: int | None) -> tuple[list[Batch], int, bool]:
        stmt = select(Batch).options(selectinload(Batch.course_version))
        if organization_id is not None:
            stmt = stmt.where(Batch.organization_id == organization_id)
        if query.status:
            stmt = stmt.where(Batch.status == query.status)
        stmt = stmt.order_by(Batch.created_at.desc() if query.sort_order == "desc" else Batch.created_at.asc())
        return await paginate(self.db, stmt, query.page, query.per_page)
