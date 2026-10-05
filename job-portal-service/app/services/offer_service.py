"""Offers: extended by a recruiter, answered by the candidate, expired by the clock."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import Actor, ApplicationStatus, OfferStatus
from app.models.application import Application
from app.models.job import Job
from app.models.offer import Offer
from app.services.application_service import ApplicationService
from app.services.outbox import write_event

S = ApplicationStatus


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class OfferService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.applications = ApplicationService(db, settings)

    async def for_application(self, application: Application) -> Offer | None:
        return (await self.db.execute(select(Offer).where(Offer.application_id == application.id))).scalar_one_or_none()

    def _event(self, event_type: str, offer: Offer, application: Application, job: Job) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="offer", aggregate_id=offer.id,
            payload={
                "offer_id": str(offer.public_id), "application_id": str(application.public_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id),
                "user_id": str(application.user_id), "organization_id": str(application.organization_id) if application.organization_id else None, "status": offer.status,
                "expires_at": _iso(offer.expires_at), "occurred_at": _iso(utcnow()),
            },
        )

    async def extend(
        self, auth: AccessTokenClaims, application: Application, job: Job, *, ctc: int, currency: str | None, joining_date: date | None, valid_days: int | None, note: str | None,
        role_title: str | None,
    ) -> Offer:
        application = await self.applications._locked(application)
        if await self.for_application(application) is not None:
            raise ConflictError("An offer has already been made on this application.", code="OFFER_EXISTS")
        await self.applications._require_job_active(job)
        await self.applications.move(application, S.OFFERED, Actor.RECRUITER, actor_user_id=auth.user_id, note="Offer extended", job=job, locked=True)
        offer = Offer(
            public_id=new_public_id(), application_id=application.id, ctc=ctc, currency=currency or job.currency, joining_date=joining_date, role_title=role_title or job.title,
            note=note, status=OfferStatus.EXTENDED, expires_at=utcnow() + timedelta(days=valid_days or self.settings.OFFER_DEFAULT_VALID_DAYS), created_by=auth.user_id,
        )
        self.db.add(offer)
        await self.db.flush()
        self._event("offer.extended", offer, application, job)
        await self.db.commit()
        return offer

    async def respond(self, user_id: int, application: Application, *, accept: bool, note: str | None) -> Offer:
        application = await self.applications._locked(application)
        if application.user_id != user_id:
            raise NotFoundError("Application not found.", code="APPLICATION_NOT_FOUND")
        offer = await self.for_application(application)
        if offer is None or application.status != S.OFFERED or offer.status != OfferStatus.EXTENDED:
            raise ConflictError("There is no open offer to answer.", code="NO_OPEN_OFFER")
        job = await self.applications.job_of(application)
        if offer.expires_at <= utcnow():
            await self._expire(offer, application, job)
            await self.db.commit()
            raise ConflictError("This offer has expired.", code="OFFER_EXPIRED")
        offer.status = OfferStatus.ACCEPTED if accept else OfferStatus.DECLINED
        offer.responded_at, offer.response_note = utcnow(), note
        await self.applications.move(application, S.OFFER_ACCEPTED if accept else S.OFFER_DECLINED, Actor.CANDIDATE, actor_user_id=user_id, note=note, job=job, locked=True)
        self._event("offer.accepted" if accept else "offer.declined", offer, application, job)
        await self.db.commit()
        return offer

    async def _expire(self, offer: Offer, application: Application, job: Job) -> None:
        offer.status, offer.responded_at = OfferStatus.EXPIRED, utcnow()
        await self.applications.move(application, S.OFFER_DECLINED, Actor.SYSTEM, actor_user_id=None, note="Offer expired unanswered", job=job, locked=True)
        self._event("offer.expired", offer, application, job)

    async def expire_due(self, *, limit: int = 200) -> int:
        """Expire offers nobody answered (run by the worker)."""
        rows = list(
            (
                await self.db.execute(
                    select(Offer).where(Offer.status == OfferStatus.EXTENDED, Offer.expires_at < utcnow()).limit(limit).with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for offer in rows:
            application = (await self.db.execute(select(Application).where(Application.id == offer.application_id).with_for_update())).scalar_one()
            if application.status != S.OFFERED:
                continue
            await self._expire(offer, application, await self.applications.job_of(application))
        await self.db.commit()
        return len(rows)
