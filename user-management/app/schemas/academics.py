"""Requests and responses for an institution's academic structure."""

from pydantic import Field

from app.schemas.common import RequestSchema, ResponseSchema, SuccessResponse
from app.schemas.types import PublicIdOut, UserId, _id_type, text

DepartmentId = _id_type("department_id", "1755000000000801")
ProgramId = _id_type("program_id", "1755000000000802")

Code = text(20, examples=["CSE"])


class DepartmentCreate(RequestSchema):
    name: text(120, min_length=2, examples=["Computer Science and Engineering"])  # type: ignore[valid-type]
    code: Code  # type: ignore[valid-type]
    head_user_id: UserId | None = Field(
        default=None, description="Head of department: a staff member of this institution"
    )


class DepartmentUpdate(RequestSchema):
    name: text(120, min_length=2) | None = None  # type: ignore[valid-type]
    code: Code | None = None  # type: ignore[valid-type]
    head_user_id: UserId | None = Field(default=None, description="Send null to clear")


class ProgramCreate(RequestSchema):
    department_id: DepartmentId  # type: ignore[valid-type]
    name: text(120, min_length=2, examples=["B.Tech Computer Science"])  # type: ignore[valid-type]
    code: Code  # type: ignore[valid-type]
    duration_years: int = Field(ge=1, le=8)


class ProgramUpdate(RequestSchema):
    department_id: DepartmentId | None = None  # type: ignore[valid-type]
    name: text(120, min_length=2) | None = None  # type: ignore[valid-type]
    code: Code | None = None  # type: ignore[valid-type]
    duration_years: int | None = Field(default=None, ge=1, le=8)


class SectionCreate(RequestSchema):
    program_id: ProgramId  # type: ignore[valid-type]
    year_of_study: int = Field(ge=1, le=8)
    name: text(20, examples=["A"])  # type: ignore[valid-type]
    class_teacher_id: UserId | None = None


class SectionUpdate(RequestSchema):
    year_of_study: int | None = Field(default=None, ge=1, le=8)
    name: text(20) | None = None  # type: ignore[valid-type]
    class_teacher_id: UserId | None = Field(default=None, description="Send null to clear")


class PlaceStudents(RequestSchema):
    add: list[UserId] = Field(
        default_factory=list, max_length=500, description="Students to put in this section (moved out of any other)"
    )
    remove: list[UserId] = Field(
        default_factory=list, max_length=500, description="Students to take out of this section"
    )


# ---------------------------------------------------------------- responses


class PersonOut(ResponseSchema):
    user_id: PublicIdOut
    full_name: str


class SectionOut(ResponseSchema):
    section_id: PublicIdOut
    program_id: PublicIdOut
    year_of_study: int
    name: str
    label: str = Field(description='e.g. "B.Tech CSE · Year 2 · A"')
    class_teacher: PersonOut | None
    student_count: int


class ProgramOut(ResponseSchema):
    program_id: PublicIdOut
    department_id: PublicIdOut
    name: str
    code: str
    duration_years: int
    sections: list[SectionOut]


class DepartmentOut(ResponseSchema):
    department_id: PublicIdOut
    name: str
    code: str
    head: PersonOut | None
    programs: list[ProgramOut]


class AcademicStructure(ResponseSchema):
    organization_id: PublicIdOut
    can_manage: bool
    departments: list[DepartmentOut]
    totals: dict[str, int] = Field(description="departments, programs, sections, placed_students")


class AcademicStructureResponse(SuccessResponse):
    academics: AcademicStructure


class SectionStudent(ResponseSchema):
    user_id: PublicIdOut
    full_name: str
    admission_number: str | None
    email: str | None


class SectionStudentsResponse(SuccessResponse):
    section: SectionOut
    students: list[SectionStudent]


class PlacedResponse(SuccessResponse):
    changed: int
