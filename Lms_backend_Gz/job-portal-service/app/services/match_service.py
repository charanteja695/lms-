"""Matching: eligibility first, then the score (docs/PRODUCT.md §5.7), stored so recommendations are a cheap query.

Two kinds of work keep the matches current, both run by the worker in short batches so no one item holds up the others:
  * ``match_job``       a job opened or changed → score every candidate against it (a batch of ``MATCH_BATCH_SIZE`` per work item,
                        continuing with a follow-up item until the candidates run out)
  * ``match_candidate`` a profile or preferences changed → score that candidate against every open job they may see

A pair that is not eligible, or scores below ``MATCH_STORE_MIN_SCORE``, has no stored match (an existing one is removed). A student
is notified (``job.match_found``) once per job, when a match first reaches ``MATCH_NOTIFY_MIN_SCORE``.

Semantic similarity uses embeddings from ai-gateway when it can, and word overlap when it cannot (the method is stored on the match).
"""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway import GatewayClient, GatewayError
from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import JobStatus, WorkKind
from app.matching import eligibility
from app.matching.model import Candidate, Eligibility, JobSpec, MatchResult, Preferences
from app.matching.scoring import Weights, score
from app.matching.text import dense_cosine, lexical_cosine, scale_dense, scale_lexical
from app.models.job import Job
from app.models.match import CandidatePreference, JobMatch
from app.models.refs import CandidateProfile
from app.services import work_service
from app.services.candidate_service import CandidateService, to_candidate, to_preferences
from app.services.job_service import JobService
from app.services.outbox import write_event

EMBED_BATCH = 64


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class MatchService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient | None = None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.weights = Weights(settings.MATCH_WEIGHT_SKILLS, settings.MATCH_WEIGHT_SEMANTIC, settings.MATCH_WEIGHT_CERTIFICATES, settings.MATCH_WEIGHT_PREFERENCES)

    # ------------------------------------------------------------------ scoring one pair
    @staticmethod
    def semantic(spec: JobSpec, candidate: Candidate, job_vector: list[float] | None, candidate_vector: list[float] | None) -> tuple[float, str, float]:
        """(similarity scaled to 0..1, method, raw cosine)."""
        if job_vector and candidate_vector and len(job_vector) == len(candidate_vector):
            cosine = dense_cosine(job_vector, candidate_vector)
            return scale_dense(cosine), "dense", cosine
        cosine = lexical_cosine(candidate.text, spec.text)
        return scale_lexical(cosine), "lexical", cosine

    def evaluate(
        self, spec: JobSpec, candidate: Candidate, prefs: Preferences, courses: dict[int, str], job_vector: list[float] | None = None, candidate_vector: list[float] | None = None
    ) -> tuple[Eligibility, MatchResult | None]:
        verdict = eligibility.check(spec, candidate, course_titles=courses)
        if not verdict.eligible:
            return verdict, None
        similarity, method, _ = self.semantic(spec, candidate, job_vector, candidate_vector)
        return verdict, score(spec, candidate, prefs, courses=courses, semantic=similarity, semantic_method=method, weights=self.weights)

    # ------------------------------------------------------------------ embeddings
    async def _embed(self, texts: list[str]) -> list[list[float]] | None:
        if self.gateway is None or not texts:
            return None
        try:
            vectors: list[list[float]] = []
            for start in range(0, len(texts), EMBED_BATCH):
                done = await self.gateway.embed(organization_id=self.settings.PLATFORM_ORGANIZATION_ID, user_id=None, texts=texts[start : start + EMBED_BATCH])
                vectors.extend(done.vectors)
            return vectors if len(vectors) == len(texts) else None
        except GatewayError:
            return None  # word overlap will do until the embedding service is back; the match records which method it used

    async def _job_vector(self, job: Job, spec: JobSpec) -> list[float] | None:
        if job.embedding and job.embedding_revision == job.revision:
            return list(job.embedding)
        vectors = await self._embed([spec.text])
        if vectors:
            job.embedding, job.embedding_revision = vectors[0], job.revision
        return vectors[0] if vectors else None

    async def _candidate_vectors(self, profiles: list[CandidateProfile]) -> dict[int, list[float]]:
        """Embed the profiles that have no current vector, in one call per ``EMBED_BATCH``."""
        stale = [p for p in profiles if not p.embedding or p.embedding_revision != p.revision]
        vectors = await self._embed([to_candidate(p).text or " " for p in stale]) if stale else None
        if vectors:
            for profile, vector in zip(stale, vectors, strict=True):
                profile.embedding, profile.embedding_revision = vector, profile.revision
        return {p.user_id: list(p.embedding) for p in profiles if p.embedding and p.embedding_revision == p.revision}

    # ------------------------------------------------------------------ storing
    async def _store(self, job: Job, candidate: Candidate, profile_revision: int, verdict: Eligibility, result: MatchResult | None, *, open_to_work: bool) -> None:
        existing = (await self.db.execute(select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == candidate.user_id))).scalar_one_or_none()
        keep = verdict.eligible and result is not None and result.score >= self.settings.MATCH_STORE_MIN_SCORE
        if not keep or result is None:
            if existing is not None:
                await self.db.delete(existing)
            return
        if existing is None:
            existing = JobMatch(job_id=job.id, user_id=candidate.user_id, notified_at=None)
            self.db.add(existing)
        existing.score, existing.breakdown, existing.explanation = result.score, result.breakdown, result.explanation
        existing.semantic_method, existing.semantic_similarity = result.semantic_method, result.semantic_similarity
        existing.job_revision, existing.profile_revision = job.revision, profile_revision
        if open_to_work and existing.notified_at is None and result.score >= self.settings.MATCH_NOTIFY_MIN_SCORE and job.status == JobStatus.OPEN:
            existing.notified_at = utcnow()
            write_event(
                self.db, event_type="job.match_found", aggregate_type="job", aggregate_id=job.id,
                payload={
                    "user_id": str(candidate.user_id), "job_id": str(job.public_id), "employer_id": str(job.employer_org_id), "title": job.title, "score": result.score,
                    "occurred_at": _iso(utcnow()),
                },
            )

    # ------------------------------------------------------------------ the two kinds of work
    async def match_job(self, job_public_id: int, *, after: int = 0) -> bool:
        """Score one batch of candidates against a job. Returns True when there may be more (a follow-up item was queued)."""
        jobs = JobService(self.db, self.settings)
        job = await jobs.get(job_public_id)
        if job.status != JobStatus.OPEN:
            return False
        spec = await jobs.spec(job)
        profiles = list(
            (await self.db.execute(select(CandidateProfile).where(CandidateProfile.user_id > after).order_by(CandidateProfile.user_id).limit(self.settings.MATCH_BATCH_SIZE))).scalars()
        )
        if not profiles:
            await self.db.commit()
            return False
        candidates = [to_candidate(p) for p in profiles]
        wanted_courses = {int(c) for c in spec.eligibility.get("certificate_course_ids") or []} | {int(m["course_id"]) for m in spec.eligibility.get("min_scores") or []}
        for c in candidates:
            wanted_courses |= c.certificate_course_ids | set(c.scores)
        courses = await CandidateService(self.db).course_titles(wanted_courses)
        prefs = {p.user_id: p for p in (await self.db.execute(select(CandidatePreference).where(CandidatePreference.user_id.in_([p.user_id for p in profiles])))).scalars()}
        job_vector = await self._job_vector(job, spec)
        vectors = await self._candidate_vectors(profiles) if job_vector else {}
        for profile, candidate in zip(profiles, candidates, strict=True):
            preference = to_preferences(prefs.get(profile.user_id))
            verdict, result = self.evaluate(spec, candidate, preference, courses, job_vector, vectors.get(profile.user_id))
            if not preference.open_to_work:
                verdict, result = Eligibility(False, ["Not open to work"]), None
            await self._store(job, candidate, profile.revision, verdict, result, open_to_work=preference.open_to_work)
        more = len(profiles) >= self.settings.MATCH_BATCH_SIZE
        if more:
            await work_service.enqueue(self.db, WorkKind.MATCH_JOB, job.public_id, {"after": profiles[-1].user_id}, dedupe=False)
        await self.db.commit()
        return more

    async def match_candidate(self, user_id: int) -> int:
        """Score one candidate against every open job they may see. Returns how many matches they have now."""
        profile = await self.db.get(CandidateProfile, user_id)
        if profile is None:
            return 0
        candidate = to_candidate(profile)
        row = await self.db.get(CandidatePreference, user_id)
        prefs = to_preferences(row)
        if not prefs.open_to_work:
            await self.db.execute(delete(JobMatch).where(JobMatch.user_id == user_id))
            await self.db.commit()
            return 0
        vectors = await self._candidate_vectors([profile])
        jobs_service = JobService(self.db, self.settings)
        jobs = list((await self.db.execute(select(Job).where(JobService.visible_to_students(candidate.organization_id)).order_by(Job.id))).scalars())
        # matches for jobs this student can no longer see (closed, paused, restricted elsewhere) are dropped
        visible_ids = {j.id for j in jobs}
        for stale in (await self.db.execute(select(JobMatch).where(JobMatch.user_id == user_id))).scalars():
            if stale.job_id not in visible_ids:
                await self.db.delete(stale)
        courses = await CandidateService(self.db).course_titles(None)
        kept = 0
        for job in jobs:
            spec = await jobs_service.spec(job)
            job_vector = await self._job_vector(job, spec)
            verdict, result = self.evaluate(spec, candidate, prefs, courses, job_vector, vectors.get(user_id) if job_vector else None)
            await self._store(job, candidate, profile.revision, verdict, result, open_to_work=True)
            kept += int(verdict.eligible and result is not None and result.score >= self.settings.MATCH_STORE_MIN_SCORE)
        await self.db.commit()
        return kept

    # ------------------------------------------------------------------ reading
    async def matches_for(self, user_id: int, organization_id: int | None, *, limit: int, offset: int = 0) -> list[tuple[Job, JobMatch]]:
        """A student's best matches among the jobs they can see right now, highest first."""
        rows = await self.db.execute(
            select(Job, JobMatch)
            .join(JobMatch, JobMatch.job_id == Job.id)
            .where(JobMatch.user_id == user_id, JobService.visible_to_students(organization_id))
            .order_by(JobMatch.score.desc(), Job.published_at.desc().nullslast(), Job.id)
            .limit(limit)
            .offset(offset)
        )
        return [(job, match) for job, match in rows.all()]

    async def match_for(self, user_id: int, job: Job) -> JobMatch | None:
        return (await self.db.execute(select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == user_id))).scalar_one_or_none()
