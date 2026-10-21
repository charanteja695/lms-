"""An institution's academic structure: departments -> programs -> sections, and the students in each section.

Read by the institution's staff and head (and its owning admin and the super admin); changed by the head (permission
``academics.manage``), the owning admin and the super admin.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentAuth, DbSession, OrganizationIdParam, RequestCtx
from app.api.responses import errors
from app.core.exceptions import NotFoundError
from app.core.ids import parse_public_id
from app.models.academics import ClassSection, Department, Program
from app.models.user import User
from app.schemas.academics import (
    AcademicStructure,
    AcademicStructureResponse,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    PersonOut,
    PlacedResponse,
    PlaceStudents,
    ProgramCreate,
    ProgramOut,
    ProgramUpdate,
    SectionCreate,
    SectionOut,
    SectionStudent,
    SectionStudentsResponse,
    SectionUpdate,
)
from app.services.academic_service import AcademicService, Access, Tree

router = APIRouter(
    prefix="/institutions/{organization_id}", tags=["Academic structure"], responses=errors(401, 403, 404)
)


def _item_id(label: str) -> object:
    async def parse(item_id: Annotated[str, Path(examples=["1755000000000801"])]) -> int:
        number = parse_public_id(item_id)
        if number is None:
            raise NotFoundError(f"{label} not found.", code=f"{label.upper()}_NOT_FOUND")
        return number

    return parse


DepartmentIdParam = Annotated[int, Depends(_item_id("Department"))]
ProgramIdParam = Annotated[int, Depends(_item_id("Program"))]
SectionIdParam = Annotated[int, Depends(_item_id("Section"))]


def _person(user: User | None) -> PersonOut | None:
    return PersonOut(user_id=user.public_id, full_name=user.full_name) if user else None


def _section_out(section: ClassSection, program: Program, department: Department, tree: Tree) -> SectionOut:
    return SectionOut(
        section_id=section.public_id,
        program_id=program.public_id,
        year_of_study=section.year_of_study,
        name=section.name,
        label=f"{program.code} · Year {section.year_of_study} · {section.name}",
        class_teacher=_person(tree.people.get(section.class_teacher_id)) if section.class_teacher_id else None,
        student_count=tree.student_counts.get(section.id, 0),
    )


def _structure(organization_id: int, access: Access, tree: Tree) -> AcademicStructure:
    departments: list[DepartmentOut] = []
    for department in tree.departments:
        programs = [
            ProgramOut(
                program_id=program.public_id,
                department_id=department.public_id,
                name=program.name,
                code=program.code,
                duration_years=program.duration_years,
                sections=[_section_out(s, program, department, tree) for s in tree.sections.get(program.id, [])],
            )
            for program in tree.programs.get(department.id, [])
        ]
        departments.append(
            DepartmentOut(
                department_id=department.public_id,
                name=department.name,
                code=department.code,
                head=_person(tree.people.get(department.head_user_id)) if department.head_user_id else None,
                programs=programs,
            )
        )
    return AcademicStructure(
        organization_id=organization_id,
        can_manage=access.can_manage,
        rights=access.rights,
        departments=departments,
        totals={
            "departments": len(tree.departments),
            "programs": sum(len(v) for v in tree.programs.values()),
            "sections": sum(len(v) for v in tree.sections.values()),
            "placed_students": sum(tree.student_counts.values()),
        },
    )


async def _respond(
    service: AcademicService, auth: CurrentAuth, organization_id: int, message: str
) -> AcademicStructureResponse:
    access = await service.access(auth.user, organization_id)
    return AcademicStructureResponse(
        message=message,
        academics=_structure(organization_id, access, await service.tree(access.institution)),
    )


@router.get(
    "/academics",
    response_model=AcademicStructureResponse,
    summary="Departments, programs and sections, with student counts",
)
async def get_structure(
    organization_id: OrganizationIdParam, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    return await _respond(AcademicService(db, ctx), auth, organization_id, "Academic structure retrieved successfully.")


# ---------------------------------------------------------------- departments
@router.post(
    "/departments",
    response_model=AcademicStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a department",
    responses=errors(409, 422),
)
async def create_department(
    organization_id: OrganizationIdParam, body: DepartmentCreate, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="create")
    await service.create_department(auth.user, access.institution, body.model_dump())
    return await _respond(service, auth, organization_id, "Department added.")


@router.patch(
    "/departments/{item_id}",
    response_model=AcademicStructureResponse,
    summary="Change a department (or its head)",
    responses=errors(409, 422),
)
async def update_department(
    organization_id: OrganizationIdParam,
    item_id: DepartmentIdParam,
    body: DepartmentUpdate,
    auth: CurrentAuth,
    db: DbSession,
    ctx: RequestCtx,
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="update")
    await service.update_department(auth.user, access.institution, item_id, body.model_dump(exclude_unset=True))
    return await _respond(service, auth, organization_id, "Department saved.")


@router.delete(
    "/departments/{item_id}",
    response_model=AcademicStructureResponse,
    summary="Remove a department with no programs",
    responses=errors(409),
)
async def delete_department(
    organization_id: OrganizationIdParam, item_id: DepartmentIdParam, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="delete")
    await service.delete_department(auth.user, access.institution, item_id)
    return await _respond(service, auth, organization_id, "Department removed.")


# ---------------------------------------------------------------- programs
@router.post(
    "/programs",
    response_model=AcademicStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a program to a department",
    responses=errors(409, 422),
)
async def create_program(
    organization_id: OrganizationIdParam, body: ProgramCreate, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="create")
    await service.create_program(auth.user, access.institution, body.model_dump())
    return await _respond(service, auth, organization_id, "Program added.")


@router.patch(
    "/programs/{item_id}",
    response_model=AcademicStructureResponse,
    summary="Change a program",
    responses=errors(409, 422),
)
async def update_program(
    organization_id: OrganizationIdParam,
    item_id: ProgramIdParam,
    body: ProgramUpdate,
    auth: CurrentAuth,
    db: DbSession,
    ctx: RequestCtx,
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="update")
    await service.update_program(auth.user, access.institution, item_id, body.model_dump(exclude_unset=True))
    return await _respond(service, auth, organization_id, "Program saved.")


@router.delete(
    "/programs/{item_id}",
    response_model=AcademicStructureResponse,
    summary="Remove a program with no sections",
    responses=errors(409),
)
async def delete_program(
    organization_id: OrganizationIdParam, item_id: ProgramIdParam, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="delete")
    await service.delete_program(auth.user, access.institution, item_id)
    return await _respond(service, auth, organization_id, "Program removed.")


# ---------------------------------------------------------------- sections
@router.post(
    "/sections",
    response_model=AcademicStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a section (a year's class of a program)",
    responses=errors(409, 422),
)
async def create_section(
    organization_id: OrganizationIdParam, body: SectionCreate, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="create")
    await service.create_section(auth.user, access.institution, body.model_dump())
    return await _respond(service, auth, organization_id, "Section added.")


@router.patch(
    "/sections/{item_id}",
    response_model=AcademicStructureResponse,
    summary="Change a section (or its class teacher)",
    responses=errors(409, 422),
)
async def update_section(
    organization_id: OrganizationIdParam,
    item_id: SectionIdParam,
    body: SectionUpdate,
    auth: CurrentAuth,
    db: DbSession,
    ctx: RequestCtx,
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="update")
    await service.update_section(auth.user, access.institution, item_id, body.model_dump(exclude_unset=True))
    return await _respond(service, auth, organization_id, "Section saved.")


@router.delete(
    "/sections/{item_id}",
    response_model=AcademicStructureResponse,
    summary="Remove an empty section",
    responses=errors(409),
)
async def delete_section(
    organization_id: OrganizationIdParam, item_id: SectionIdParam, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> AcademicStructureResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="delete")
    await service.delete_section(auth.user, access.institution, item_id)
    return await _respond(service, auth, organization_id, "Section removed.")


@router.get("/sections/{item_id}/students", response_model=SectionStudentsResponse, summary="The students in a section")
async def section_students(
    organization_id: OrganizationIdParam, item_id: SectionIdParam, auth: CurrentAuth, db: DbSession, ctx: RequestCtx
) -> SectionStudentsResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id)
    section, students = await service.section_students(access.institution, item_id)
    tree = await service.tree(access.institution)
    program = next(p for group in tree.programs.values() for p in group if p.id == section.program_id)
    department = next(d for d in tree.departments if d.id == program.department_id)
    return SectionStudentsResponse(
        message="Section students retrieved successfully.",
        section=_section_out(section, program, department, tree),
        students=[
            SectionStudent(
                user_id=s.public_id,
                full_name=s.full_name,
                admission_number=s.student.admission_number if s.student else None,
                email=s.email,
            )
            for s in students
        ],
    )


@router.put(
    "/sections/{item_id}/students",
    response_model=PlacedResponse,
    summary="Put students in (or take them out of) a section",
    responses=errors(422),
)
async def place_students(
    organization_id: OrganizationIdParam,
    item_id: SectionIdParam,
    body: PlaceStudents,
    auth: CurrentAuth,
    db: DbSession,
    ctx: RequestCtx,
) -> PlacedResponse:
    service = AcademicService(db, ctx)
    access = await service.access(auth.user, organization_id, manage="update")
    changed = await service.place_students(auth.user, access.institution, item_id, body.add, body.remove)
    return PlacedResponse(message=f"{changed} student{'s' if changed != 1 else ''} updated.", changed=changed)
