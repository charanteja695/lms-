"""Controlled vocabularies used in requests, responses and storage.

Stored as strings, so adding a value never needs a database type migration.
Never rename or remove a value that is already stored; add a new one instead.
"""

from enum import StrEnum


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class GuardianRelationship(StrEnum):
    FATHER = "father"
    MOTHER = "mother"
    LEGAL_GUARDIAN = "legal_guardian"
    GRANDPARENT = "grandparent"
    SIBLING = "sibling"
    OTHER = "other"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    VISITING = "visiting"
    INTERN = "intern"


class InstitutionType(StrEnum):
    SCHOOL = "school"
    COLLEGE = "college"
    UNIVERSITY = "university"
    COACHING_CENTER = "coaching_center"
    TRAINING_INSTITUTE = "training_institute"
    OTHER = "other"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
