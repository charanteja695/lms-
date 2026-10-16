"""The prompt registry's lifecycle: draft -> active -> retired (docs/PRODUCT.md §6: "prompt registry + versions").

Mirrors certificate-service's template review in spirit — a person other than the one who wrote a version
activates it, so a prompt that will be sent to every student in a course gets a second set of eyes — but with a
single ACTIVE version per prompt (not per-course, so activating one retires whatever was active before) rather
than certificate-service's "per course, plus a platform default" scoping, which this registry has no equivalent of.
"""

from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.db.session import flush_or_conflict
from app.domain.enums import PromptStatus
from app.models.prompt import Prompt, PromptVersion
from app.prompt.render import placeholders_in


class PromptService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_prompt(self, *, key: str, capability: str, owner_service: str, description: str, created_by: int) -> Prompt:
        prompt = Prompt(public_id=new_public_id(), key=key, capability=capability, owner_service=owner_service, description=description, created_by=created_by)
        self.db.add(prompt)
        await flush_or_conflict(self.db, f'A prompt with the key "{key}" already exists.')
        await self.db.commit()
        return prompt

    async def get_prompt(self, key: str) -> Prompt:
        prompt = (await self.db.execute(select(Prompt).where(Prompt.key == key))).scalar_one_or_none()
        if prompt is None:
            raise NotFoundError(f'Prompt "{key}" not found.', code="PROMPT_NOT_FOUND")
        return prompt

    async def list_prompts(self, *, page: int, per_page: int) -> tuple[list[Prompt], int, bool]:
        return await paginate(self.db, select(Prompt).order_by(Prompt.created_at.desc(), Prompt.id), page, per_page)

    async def list_versions(self, prompt: Prompt) -> list[PromptVersion]:
        """Every version of a prompt, newest first (drafts, the active one, retired ones)."""
        stmt = select(PromptVersion).where(PromptVersion.prompt_id == prompt.id).order_by(PromptVersion.version.desc())
        return list((await self.db.execute(stmt)).scalars())

    async def active_version(self, prompt: Prompt) -> PromptVersion:
        version = (
            await self.db.execute(select(PromptVersion).where(PromptVersion.prompt_id == prompt.id, PromptVersion.status == PromptStatus.ACTIVE))
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError(f'Prompt "{prompt.key}" has no active version.', code="NO_ACTIVE_VERSION")
        return version

    async def get_version(self, prompt: Prompt, version: int) -> PromptVersion:
        row = (
            await self.db.execute(select(PromptVersion).where(PromptVersion.prompt_id == prompt.id, PromptVersion.version == version))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f'Prompt "{prompt.key}" has no version {version}.', code="PROMPT_VERSION_NOT_FOUND")
        return row

    async def create_version(
        self, prompt: Prompt, *, template: str, variables: list[str], allowed_tools: list[str], model_params: dict[str, object], created_by: int
    ) -> PromptVersion:
        missing = placeholders_in(template) - set(variables)
        if missing:
            raise ValidationFailedError(
                f"The template uses placeholder(s) not listed in variables: {', '.join(sorted(missing))}.", code="UNDECLARED_VARIABLE"
            )
        last = (
            await self.db.execute(select(PromptVersion.version).where(PromptVersion.prompt_id == prompt.id).order_by(PromptVersion.version.desc()).limit(1))
        ).scalar_one_or_none()
        version = PromptVersion(
            public_id=new_public_id(),
            prompt_id=prompt.id,
            version=(last or 0) + 1,
            template=template,
            variables=variables,
            allowed_tools=allowed_tools,
            model_params=model_params,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.commit()
        return version

    async def activate_version(
        self, prompt: Prompt, version: PromptVersion, *, activated_by: int, self_approval: bool = False
    ) -> PromptVersion:
        """Someone other than the author activates a version; the super admin, who runs AI alone, may activate their own."""
        if version.status != PromptStatus.DRAFT:
            raise ConflictError(f"Version {version.version} is {version.status}, not draft.", code="NOT_DRAFT")
        if version.created_by == activated_by and not self_approval:
            raise PermissionDeniedError("A prompt version must be activated by someone other than its author.", code="SAME_AUTHOR")
        previous = (
            await self.db.execute(select(PromptVersion).where(PromptVersion.prompt_id == prompt.id, PromptVersion.status == PromptStatus.ACTIVE))
        ).scalar_one_or_none()
        if previous is not None:
            previous.status = PromptStatus.RETIRED
            previous.retired_by = activated_by
        version.status = PromptStatus.ACTIVE
        version.activated_by = activated_by
        await self.db.commit()
        return version

    async def retire_version(self, version: PromptVersion, *, retired_by: int) -> PromptVersion:
        if version.status == PromptStatus.RETIRED:
            return version
        version.status = PromptStatus.RETIRED
        version.retired_by = retired_by
        await self.db.commit()
        return version
