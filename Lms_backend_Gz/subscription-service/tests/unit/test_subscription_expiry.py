from datetime import timedelta

import fakeredis.aioredis
from sqlalchemy import select

from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.domain.enums import SubscriptionStatus
from app.models import Base
from app.models.course_ref import CourseRef
from app.models.institution_ref import InstitutionRef
from app.models.outbox_event import OutboxEvent
from app.models.subscription import Subscription
from app.services.subscription_service import SubscriptionService
from tests.conftest import _settings


async def test_expire_due_marks_lapsed_subscriptions_and_leaves_current_ones() -> None:
    settings = _settings()
    engine = build_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = build_sessionmaker(engine)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async with sessionmaker() as db:
        db.add(InstitutionRef(organization_id=1, name="A School", code="A-1"))
        db.add(CourseRef(course_id=1, title="Course One", slug="course-one"))
        db.add(CourseRef(course_id=2, title="Course Two", slug="course-two"))
        await db.flush()

        lapsed = Subscription(
            public_id=new_public_id(), organization_id=1, course_id=1, seats_total=10,
            starts_at=utcnow() - timedelta(days=400), ends_at=utcnow() - timedelta(days=1), created_by=1,
        )
        current = Subscription(
            public_id=new_public_id(), organization_id=1, course_id=2, seats_total=10,
            starts_at=utcnow(), ends_at=utcnow() + timedelta(days=364), created_by=1,
        )
        db.add_all([lapsed, current])
        await db.commit()

        expired_count = await SubscriptionService(db, settings, redis).expire_due()
        assert expired_count == 1

        await db.refresh(lapsed)
        await db.refresh(current)
        assert lapsed.status == SubscriptionStatus.EXPIRED
        assert current.status == SubscriptionStatus.ACTIVE

        events = (await db.execute(select(OutboxEvent))).scalars().all()
        expired = next(e for e in events if e.event_type == "subscription.expired")
        assert expired.payload["organization_id"] == str(lapsed.organization_id)  # notification-service addresses it from this
        assert expired.payload["course_id"] == str(lapsed.course_id)

    await engine.dispose()
    await redis.aclose()
