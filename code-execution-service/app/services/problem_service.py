from typing import Any

from lms_common.pagination import contains_pattern, paginate
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.crypto import SecretCipher
from app.core.exceptions import BadRequestError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.session import commit_or_conflict
from app.domain.enums import CompareMode, JobStatus, LanguageKind, ProblemStatus, ProblemType, Verdict
from app.models.language import Language
from app.models.problem import Problem
from app.models.submission import Submission
from app.schemas.common import ProblemQuery
from app.schemas.problem import ProblemCreate, ProblemUpdate
from app.services.test_case_service import check_compare_mode

_KIND_OF_TYPE = {ProblemType.CODE: LanguageKind.PROGRAM, ProblemType.SQL: LanguageKind.SQL}


class ProblemService:
    def __init__(self, db: AsyncSession, settings: Settings, cipher: SecretCipher) -> None:
        self.db = db
        self.settings = settings
        self.cipher = cipher

    # ------------------------------------------------------------------ authoring

    async def create(self, actor_user_id: int, data: ProblemCreate) -> Problem:
        problem_type = ProblemType(data.problem_type)
        self._validate_limits(data.time_limit_ms, data.memory_limit_mb)
        await self._validate_allowed_languages(data.allowed_languages, problem_type)
        if data.setup_sql and problem_type != ProblemType.SQL:
            raise ValidationFailedError(
                details=[{"field": "setup_sql", "code": "SETUP_SQL_NOT_ALLOWED", "message": "Only SQL problems have a setup script"}]
            )
        compare_mode = data.compare_mode
        if problem_type == ProblemType.SQL and "compare_mode" not in data.model_fields_set:
            compare_mode = CompareMode.ROWS_UNORDERED
        check_compare_mode(problem_type, compare_mode)
        problem = Problem(
            public_id=new_public_id(),
            title=data.title,
            statement=data.statement,
            problem_type=problem_type,
            difficulty=data.difficulty,
            tags=list(dict.fromkeys(data.tags)),
            time_limit_ms=data.time_limit_ms,
            memory_limit_mb=data.memory_limit_mb,
            allowed_languages=list(dict.fromkeys(data.allowed_languages)),
            setup_sql_encrypted=self.cipher.encrypt(data.setup_sql) if data.setup_sql else None,
            compare_mode=compare_mode,
            float_tolerance=data.float_tolerance,
            created_by=actor_user_id,
        )
        self.db.add(problem)
        await commit_or_conflict(self.db)
        return await self.get(problem.public_id)

    async def update(self, problem: Problem, data: ProblemUpdate) -> Problem:
        self._ensure_draft(problem)
        fields = data.model_fields_set
        if {"time_limit_ms", "memory_limit_mb"} & fields:
            self._validate_limits(
                data.time_limit_ms if data.time_limit_ms is not None else problem.time_limit_ms,
                data.memory_limit_mb if data.memory_limit_mb is not None else problem.memory_limit_mb,
            )
        if "allowed_languages" in fields and data.allowed_languages is not None:
            await self._validate_allowed_languages(data.allowed_languages, ProblemType(problem.problem_type))
        if "compare_mode" in fields and data.compare_mode is not None:
            check_compare_mode(problem.problem_type, data.compare_mode)
        if "setup_sql" in fields:
            if data.setup_sql and problem.problem_type != ProblemType.SQL:
                raise ValidationFailedError(
                    details=[{"field": "setup_sql", "code": "SETUP_SQL_NOT_ALLOWED", "message": "Only SQL problems have a setup script"}]
                )
            problem.setup_sql_encrypted = self.cipher.encrypt(data.setup_sql) if data.setup_sql else None

        for name in ("title", "statement", "difficulty", "time_limit_ms", "memory_limit_mb", "compare_mode", "float_tolerance"):
            value = getattr(data, name)
            if name in fields and value is not None:
                setattr(problem, name, value)
        if "tags" in fields and data.tags is not None:
            problem.tags = list(dict.fromkeys(data.tags))
        if "allowed_languages" in fields and data.allowed_languages is not None:
            problem.allowed_languages = list(dict.fromkeys(data.allowed_languages))
        problem.updated_at = utcnow()
        await commit_or_conflict(self.db)
        return await self.get(problem.public_id)

    async def publish(self, problem: Problem) -> Problem:
        self._ensure_draft(problem)
        issues: list[dict[str, str]] = []
        if not problem.test_cases:
            issues.append({"field": "test_cases", "code": "NO_TEST_CASES", "message": "Add at least one test case before publishing"})
        if problem.allowed_languages:
            enabled = {
                language.code
                for language in (
                    await self.db.execute(select(Language).where(Language.enabled.is_(True)))
                ).scalars()
            }
            missing = [code for code in problem.allowed_languages if code not in enabled]
            if missing:
                issues.append(
                    {"field": "allowed_languages", "code": "LANGUAGE_UNAVAILABLE", "message": f"Not enabled: {', '.join(missing)}"}
                )
        if issues:
            raise ValidationFailedError("This problem cannot be published yet.", details=issues)
        problem.status = ProblemStatus.PUBLISHED
        problem.published_at = utcnow()
        await commit_or_conflict(self.db)
        return problem

    async def retire(self, problem: Problem) -> Problem:
        if problem.status != ProblemStatus.PUBLISHED:
            raise BadRequestError("Only a published problem can be retired.", code="PROBLEM_NOT_PUBLISHED")
        problem.status = ProblemStatus.RETIRED
        problem.retired_at = utcnow()
        await commit_or_conflict(self.db)
        return problem

    async def delete(self, problem: Problem) -> None:
        self._ensure_draft(problem, message="Only a draft can be deleted. Retire a published problem instead.")
        await self.db.delete(problem)
        await self.db.commit()

    # ------------------------------------------------------------------ reading

    async def get(self, public_id: int) -> Problem:
        problem = (
            await self.db.execute(
                select(Problem).where(Problem.public_id == public_id).options(selectinload(Problem.test_cases))
            )
        ).scalar_one_or_none()
        if problem is None:
            raise NotFoundError("Problem not found.", code="PROBLEM_NOT_FOUND")
        return problem

    async def get_visible(self, public_id: int, *, is_reviewer: bool) -> Problem:
        """Students see published problems only; a draft or retired one does not exist for them."""
        problem = await self.get(public_id)
        if not is_reviewer and problem.status != ProblemStatus.PUBLISHED:
            raise NotFoundError("Problem not found.", code="PROBLEM_NOT_FOUND")
        return problem

    async def list_problems(
        self, query: ProblemQuery, *, is_reviewer: bool, solved_ids: set[int] | None = None
    ) -> tuple[list[Problem], int, bool]:
        stmt = select(Problem)
        if is_reviewer:
            if query.status:
                stmt = stmt.where(Problem.status == query.status)
        else:
            stmt = stmt.where(Problem.status == ProblemStatus.PUBLISHED)
        if query.difficulty:
            stmt = stmt.where(Problem.difficulty == query.difficulty)
        if query.problem_type:
            stmt = stmt.where(Problem.problem_type == query.problem_type)
        if query.tag:
            stmt = stmt.where(cast(Problem.tags, String).like(f'%"{query.tag.strip().lower()}"%'))
        if query.search:
            stmt = stmt.where(Problem.title.ilike(contains_pattern(query.search), escape="\\"))
        if query.solved is not None and solved_ids is not None:
            if query.solved:
                stmt = stmt.where(Problem.public_id.in_(solved_ids))  # an empty set matches nothing
            elif solved_ids:
                stmt = stmt.where(Problem.public_id.not_in(solved_ids))
        stmt = stmt.order_by(Problem.created_at.desc() if query.sort_order == "desc" else Problem.created_at.asc(), Problem.id)
        return await paginate(self.db, stmt, query.page, query.per_page, options=[selectinload(Problem.test_cases)])

    async def user_progress(self, user_id: int, problem_ids: list[int] | None = None) -> tuple[set[int], set[int]]:
        """``(solved, attempted)`` problem public ids for one user, optionally within a set of problems."""
        base = select(Submission.problem_public_id, Submission.verdict).where(
            Submission.user_id == user_id, Submission.status == JobStatus.COMPLETED
        )
        if problem_ids is not None:
            base = base.where(Submission.problem_public_id.in_(problem_ids))
        rows = (await self.db.execute(base.distinct())).all()
        attempted = {problem_id for problem_id, _ in rows}
        solved = {problem_id for problem_id, verdict in rows if verdict == Verdict.ACCEPTED}
        return solved, attempted

    async def stats(self, problem: Problem) -> dict[str, Any]:
        rows = (
            await self.db.execute(
                select(Submission.verdict, func.count())
                .where(Submission.problem_id == problem.id, Submission.status == JobStatus.COMPLETED)
                .group_by(Submission.verdict)
            )
        ).all()
        verdicts = {verdict or "unknown": count for verdict, count in rows}
        total = sum(verdicts.values())
        accepted = verdicts.get(Verdict.ACCEPTED, 0)
        solvers = (
            await self.db.execute(
                select(func.count(func.distinct(Submission.user_id))).where(
                    Submission.problem_id == problem.id, Submission.verdict == Verdict.ACCEPTED
                )
            )
        ).scalar_one()
        flagged = (
            await self.db.execute(
                select(func.count()).where(Submission.problem_id == problem.id, Submission.flagged.is_(True))
            )
        ).scalar_one()
        return {
            "submissions": total,
            "accepted": accepted,
            "acceptance_percent": round(100 * accepted / total) if total else 0,
            "solvers": int(solvers),
            "flagged": int(flagged),
            "verdicts": verdicts,
        }

    def decrypt_setup(self, problem: Problem) -> str:
        return self.cipher.decrypt(problem.setup_sql_encrypted) if problem.setup_sql_encrypted else ""

    # ------------------------------------------------------------------ validation

    @staticmethod
    def _ensure_draft(problem: Problem, message: str = "A published problem is frozen. Retire it and author a new one.") -> None:
        if problem.status != ProblemStatus.DRAFT:
            raise BadRequestError(message, code="PROBLEM_NOT_DRAFT")

    def _validate_limits(self, time_limit_ms: int, memory_limit_mb: int) -> None:
        details = []
        if time_limit_ms > self.settings.PROBLEM_MAX_TIME_LIMIT_MS:
            details.append({"field": "time_limit_ms", "code": "TIME_LIMIT_TOO_HIGH", "message": f"At most {self.settings.PROBLEM_MAX_TIME_LIMIT_MS} ms"})
        if memory_limit_mb > self.settings.PROBLEM_MAX_MEMORY_MB:
            details.append({"field": "memory_limit_mb", "code": "MEMORY_LIMIT_TOO_HIGH", "message": f"At most {self.settings.PROBLEM_MAX_MEMORY_MB} MB"})
        if details:
            raise ValidationFailedError(details=details)

    async def _validate_allowed_languages(self, codes: list[str], problem_type: ProblemType) -> None:
        if not codes:
            return
        languages = {
            language.code: language
            for language in (await self.db.execute(select(Language).where(Language.code.in_(codes)))).scalars()
        }
        details = []
        for code in dict.fromkeys(codes):
            language = languages.get(code)
            if language is None:
                details.append({"field": "allowed_languages", "code": "LANGUAGE_NOT_FOUND", "message": f"Unknown language: {code}"})
            elif language.kind != _KIND_OF_TYPE[problem_type]:
                details.append({"field": "allowed_languages", "code": "LANGUAGE_KIND_MISMATCH", "message": f"{code} cannot be used for a {problem_type.value} problem"})
        if details:
            raise ValidationFailedError(details=details)


def allowed_language_codes(problem: Problem, enabled: list[Language]) -> set[str]:
    """Enabled languages of the problem's type, narrowed by the author's list if there is one."""
    kind = _KIND_OF_TYPE[ProblemType(problem.problem_type)]
    codes = {language.code for language in enabled if language.kind == kind}
    return codes & set(problem.allowed_languages) if problem.allowed_languages else codes
