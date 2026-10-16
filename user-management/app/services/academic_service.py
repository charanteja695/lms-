"""An institution's academic structure (departments -> programs -> sections) and which students sit in which section.

Who may: read — the super admin, the owning admin, and the institution's members holding ``academics.view`` or
``academics.manage``; change — the super admin, the owning admin, and members holding ``academics.manage`` (by
default the institute head). Everything is scoped to one institution: an id from another institution is a 404.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.db.session import commit_or_conflict
from app.models.academics import ClassSection, Department, Program
from app.models.institution import Institution
from app.models.profiles import StudentProfile
from app.models.user import User
from app.permissions import policies
from app.permissions.roles import OrganizationType, Role, UserStatus
from app.repositories.institution_repository import InstitutionRepository
from app.repositories.user_repository import USER_LIST_OPTIONS, UserRepository
from app.services.audit_service import AuditAction, AuditService
from app.services.permission_service import PermissionService

_TEACHING_ROLES = (Role.INSTITUTION_HEAD, Role.STAFF)


@dataclass(frozen=True, slots=True)
class Access:
    institution: Institution
    can_manage: bool


@dataclass(slots=True)
class Tree:
    departments: list[Department]
    programs: dict[uuid.UUID, list[Program]]
    sections: dict[uuid.UUID, list[ClassSection]]
    people: dict[uuid.UUID, User]
    student_counts: dict[uuid.UUID, int]


def _detail(field: str, code: str, message: str) -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


class AcademicService:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.institutions = InstitutionRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db, ctx)

    # ================================================================== access

    async def access(self, actor: User, organization_id: int, *, manage: bool = False) -> Access:
        institution = await self.institutions.get_by_public_id(organization_id)
        if (
            institution is None
            or institution.org_type != OrganizationType.INSTITUTION
            or not policies.can_access_institution(actor, institution)
        ):
            raise NotFoundError("Institution not found.", code="INSTITUTION_NOT_FOUND")
        if policies.can_manage_institution(actor, institution):
            can_manage = True  # the super admin, or the admin who owns it
        else:
            held = set(await PermissionService(self.db).effective_for(actor))
            if not held & {"academics.view", "academics.manage"}:
                raise PermissionDeniedError("You cannot see this institution's academic structure.")
            can_manage = "academics.manage" in held
        if manage and not can_manage:
            raise PermissionDeniedError("Only the institute head (or its admin) changes the academic structure.")
        return Access(institution, can_manage)

    # ================================================================== reading

    async def tree(self, institution: Institution) -> Tree:
        departments = list(
            (
                await self.db.execute(
                    select(Department).where(Department.institution_id == institution.id).order_by(Department.name)
                )
            ).scalars()
        )
        programs: dict[uuid.UUID, list[Program]] = defaultdict(list)
        for program in (
            await self.db.execute(
                select(Program).where(Program.institution_id == institution.id).order_by(Program.name)
            )
        ).scalars():
            programs[program.department_id].append(program)
        sections: dict[uuid.UUID, list[ClassSection]] = defaultdict(list)
        for section in (
            await self.db.execute(
                select(ClassSection)
                .where(ClassSection.institution_id == institution.id)
                .order_by(ClassSection.year_of_study, ClassSection.name)
            )
        ).scalars():
            sections[section.program_id].append(section)
        counts = dict(
            (
                await self.db.execute(
                    select(StudentProfile.class_section_id, func.count())
                    .join(User, User.id == StudentProfile.user_id)
                    .where(
                        StudentProfile.institution_id == institution.id,
                        StudentProfile.class_section_id.is_not(None),
                        User.deleted_at.is_(None),
                    )
                    .group_by(StudentProfile.class_section_id)
                )
            ).tuples().all()
        )
        people_ids = {d.head_user_id for d in departments if d.head_user_id} | {
            s.class_teacher_id for group in sections.values() for s in group if s.class_teacher_id
        }
        people = (
            {u.id: u for u in (await self.db.execute(select(User).where(User.id.in_(people_ids)))).scalars()}
            if people_ids
            else {}
        )
        return Tree(departments, programs, sections, people, {k: v for k, v in counts.items() if k is not None})

    async def section_students(self, institution: Institution, section_id: int) -> tuple[ClassSection, list[User]]:
        section = await self._section(institution, section_id)
        students = list(
            (
                await self.db.execute(
                    select(User)
                    .join(StudentProfile, StudentProfile.user_id == User.id)
                    .where(StudentProfile.class_section_id == section.id, User.deleted_at.is_(None))
                    .options(*USER_LIST_OPTIONS)
                    .order_by(User.first_name, User.last_name)
                )
            )
            .unique()
            .scalars()
        )
        return section, students

    # ================================================================== departments

    async def create_department(self, actor: User, institution: Institution, data: dict[str, Any]) -> Department:
        department = Department(
            institution_id=institution.id,
            name=data["name"],
            code=data["code"].upper(),
            head_user_id=await self._teacher(institution, data.get("head_user_id"), "head_user_id"),
        )
        self.db.add(department)
        self._log(actor, institution, "department.created", {"code": department.code})
        await commit_or_conflict(self.db, "A department with this code already exists here.")
        return department

    async def update_department(
        self, actor: User, institution: Institution, department_id: int, data: dict[str, Any]
    ) -> Department:
        department = await self._department(institution, department_id)
        if "name" in data and data["name"] is not None:
            department.name = data["name"]
        if "code" in data and data["code"] is not None:
            department.code = data["code"].upper()
        if "head_user_id" in data:
            department.head_user_id = await self._teacher(institution, data["head_user_id"], "head_user_id")
        self._log(actor, institution, "department.updated", {"code": department.code})
        await commit_or_conflict(self.db, "A department with this code already exists here.")
        return department

    async def delete_department(self, actor: User, institution: Institution, department_id: int) -> None:
        department = await self._department(institution, department_id)
        if await self._exists(select(Program.id).where(Program.department_id == department.id)):
            raise ConflictError("Remove or move this department's programs first.", code="DEPARTMENT_HAS_PROGRAMS")
        await self.db.delete(department)
        self._log(actor, institution, "department.deleted", {"code": department.code})
        await self.db.commit()

    # ================================================================== programs

    async def create_program(self, actor: User, institution: Institution, data: dict[str, Any]) -> Program:
        department = await self._department(institution, data["department_id"], field="department_id")
        program = Program(
            institution_id=institution.id,
            department_id=department.id,
            name=data["name"],
            code=data["code"].upper(),
            duration_years=data["duration_years"],
        )
        self.db.add(program)
        self._log(actor, institution, "program.created", {"code": program.code})
        await commit_or_conflict(self.db, "A program with this code already exists here.")
        return program

    async def update_program(
        self, actor: User, institution: Institution, program_id: int, data: dict[str, Any]
    ) -> Program:
        program = await self._program(institution, program_id)
        if data.get("department_id") is not None:
            program.department_id = (
                await self._department(institution, data["department_id"], field="department_id")
            ).id
        for name in ("name", "duration_years"):
            if data.get(name) is not None:
                setattr(program, name, data[name])
        if data.get("code") is not None:
            program.code = data["code"].upper()
        if data.get("duration_years") is not None and await self._exists(
            select(ClassSection.id).where(
                ClassSection.program_id == program.id, ClassSection.year_of_study > program.duration_years
            )
        ):
            raise ValidationFailedError(
                details=[
                    _detail("duration_years", "SECTIONS_BEYOND_DURATION", "Some sections are in a later year than this")
                ]
            )
        self._log(actor, institution, "program.updated", {"code": program.code})
        await commit_or_conflict(self.db, "A program with this code already exists here.")
        await self._refresh_students(institution, program_id=program.id)
        return program

    async def delete_program(self, actor: User, institution: Institution, program_id: int) -> None:
        program = await self._program(institution, program_id)
        if await self._exists(select(ClassSection.id).where(ClassSection.program_id == program.id)):
            raise ConflictError("Remove this program's sections first.", code="PROGRAM_HAS_SECTIONS")
        await self.db.delete(program)
        self._log(actor, institution, "program.deleted", {"code": program.code})
        await self.db.commit()

    # ================================================================== sections

    async def create_section(self, actor: User, institution: Institution, data: dict[str, Any]) -> ClassSection:
        program = await self._program(institution, data["program_id"], field="program_id")
        if data["year_of_study"] > program.duration_years:
            raise ValidationFailedError(
                details=[
                    _detail("year_of_study", "BEYOND_DURATION", f"{program.name} runs {program.duration_years} years")
                ]
            )
        section = ClassSection(
            institution_id=institution.id,
            program_id=program.id,
            year_of_study=data["year_of_study"],
            name=data["name"].upper(),
            class_teacher_id=await self._teacher(institution, data.get("class_teacher_id"), "class_teacher_id"),
        )
        self.db.add(section)
        self._log(
            actor,
            institution,
            "section.created",
            {"program": program.code, "year": section.year_of_study, "name": section.name},
        )
        await commit_or_conflict(self.db, "This program already has that section in that year.")
        return section

    async def update_section(
        self, actor: User, institution: Institution, section_id: int, data: dict[str, Any]
    ) -> ClassSection:
        section = await self._section(institution, section_id)
        program = await self.db.get(Program, section.program_id)
        assert program is not None
        if data.get("year_of_study") is not None:
            if data["year_of_study"] > program.duration_years:
                raise ValidationFailedError(
                    details=[
                        _detail(
                            "year_of_study", "BEYOND_DURATION", f"{program.name} runs {program.duration_years} years"
                        )
                    ]
                )
            section.year_of_study = data["year_of_study"]
        if data.get("name") is not None:
            section.name = data["name"].upper()
        if "class_teacher_id" in data:
            section.class_teacher_id = await self._teacher(institution, data["class_teacher_id"], "class_teacher_id")
        self._log(actor, institution, "section.updated", {"name": section.name})
        await commit_or_conflict(self.db, "This program already has that section in that year.")
        await self._refresh_students(institution, section_id=section.id)
        return section

    async def delete_section(self, actor: User, institution: Institution, section_id: int) -> None:
        section = await self._section(institution, section_id)
        if await self._exists(select(StudentProfile.user_id).where(StudentProfile.class_section_id == section.id)):
            raise ConflictError("Move this section's students to another section first.", code="SECTION_HAS_STUDENTS")
        await self.db.delete(section)
        self._log(actor, institution, "section.deleted", {"name": section.name})
        await self.db.commit()

    async def place_students(
        self, actor: User, institution: Institution, section_id: int, add: list[int], remove: list[int]
    ) -> int:
        """Put students in this section (moving them out of any other) or take them out. Returns how many changed."""
        section = await self._section(institution, section_id)
        program = await self.db.get(Program, section.program_id)
        department = await self.db.get(Department, program.department_id) if program else None
        assert program is not None and department is not None
        wanted = {*add, *remove}
        rows = list(
            (await self.db.execute(select(User).where(User.public_id.in_(wanted)).options(*USER_LIST_OPTIONS)))
            .unique()
            .scalars()
        )
        found = {u.public_id: u for u in rows}
        bad = [
            str(pid)
            for pid in wanted
            if pid not in found
            or found[pid].role != Role.STUDENT
            or found[pid].institution_id != institution.id
            or found[pid].deleted_at is not None
            or found[pid].student is None
        ]
        if bad:
            raise ValidationFailedError(
                details=[
                    _detail(
                        "user_ids", "NOT_A_STUDENT_HERE", f"Not a student of this institution: {', '.join(sorted(bad))}"
                    )
                ]
            )
        changed = 0
        for pid in add:
            student = found[pid].student
            assert student is not None
            if student.class_section_id != section.id:
                student.class_section_id = section.id
                changed += 1
            _fill(student, department, program, section)
        for pid in remove:
            student = found[pid].student
            assert student is not None
            if student.class_section_id == section.id:
                student.class_section_id = None
                changed += 1
        for pid in wanted:
            self._user_event(found[pid], institution)
        self._log(
            actor,
            institution,
            "section.students_changed",
            {"section": section.name, "added": len(add), "removed": len(remove)},
        )
        await self.db.commit()
        return changed

    # ================================================================== helpers

    async def _refresh_students(
        self, institution: Institution, *, program_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None
    ) -> None:
        """A renamed program/section/department rewrites the text fields of the students placed under it."""
        stmt = (
            select(StudentProfile, ClassSection, Program, Department)
            .join(ClassSection, ClassSection.id == StudentProfile.class_section_id)
            .join(Program, Program.id == ClassSection.program_id)
            .join(Department, Department.id == Program.department_id)
            .where(StudentProfile.institution_id == institution.id)
        )
        if program_id is not None:
            stmt = stmt.where(Program.id == program_id)
        if section_id is not None:
            stmt = stmt.where(ClassSection.id == section_id)
        for student, section, program, department in (await self.db.execute(stmt)).tuples():
            _fill(student, department, program, section)
        await self.db.commit()

    async def _exists(self, stmt: Any) -> bool:
        return (await self.db.execute(stmt.limit(1))).first() is not None

    async def _department(self, institution: Institution, public_id: int, *, field: str | None = None) -> Department:
        row = (
            await self.db.execute(
                select(Department).where(Department.public_id == public_id, Department.institution_id == institution.id)
            )
        ).scalar_one_or_none()
        return row if row is not None else self._missing("Department", field)

    async def _program(self, institution: Institution, public_id: int, *, field: str | None = None) -> Program:
        row = (
            await self.db.execute(
                select(Program).where(Program.public_id == public_id, Program.institution_id == institution.id)
            )
        ).scalar_one_or_none()
        return row if row is not None else self._missing("Program", field)

    async def _section(self, institution: Institution, public_id: int) -> ClassSection:
        row = (
            await self.db.execute(
                select(ClassSection).where(
                    ClassSection.public_id == public_id, ClassSection.institution_id == institution.id
                )
            )
        ).scalar_one_or_none()
        return row if row is not None else self._missing("Section", None)

    @staticmethod
    def _missing(label: str, field: str | None) -> Any:
        if field:  # a bad reference inside a request body is a validation error on that field
            raise ValidationFailedError(
                details=[_detail(field, "NOT_FOUND", f"No such {label.lower()} in this institution")]
            )
        raise NotFoundError(f"{label} not found.", code=f"{label.upper()}_NOT_FOUND")

    async def _teacher(self, institution: Institution, public_id: int | None, field: str) -> uuid.UUID | None:
        """A head of department or class teacher: an active staff member or the head of this institution."""
        if public_id is None:
            return None
        user = await self.users.get_by_public_id(public_id)
        if (
            user is None
            or user.institution_id != institution.id
            or user.role not in _TEACHING_ROLES
            or user.status != UserStatus.ACTIVE
        ):
            raise ValidationFailedError(
                details=[_detail(field, "NOT_STAFF_HERE", "Choose an active staff member of this institution")]
            )
        return user.id

    def _log(self, actor: User, institution: Institution, what: str, details: dict[str, Any]) -> None:
        self.audit.log(
            AuditAction.INSTITUTION_UPDATED,
            actor_id=actor.id,
            resource_type="institution",
            resource_id=institution.id,
            institution_id=institution.id,
            details={"academics": what, **details},
        )

    def _user_event(self, user: User, institution: Institution) -> None:
        self.audit.event(
            "user.updated",
            aggregate_type="user",
            aggregate_id=user.id,
            payload=self.users.event_payload(user, institution_public_id=institution.public_id),
        )


def _fill(student: StudentProfile, department: Department, program: Program, section: ClassSection) -> None:
    student.program = program.name[:100]
    student.branch = department.name[:100]
    student.year_of_study = section.year_of_study
    student.section = section.name[:20]
