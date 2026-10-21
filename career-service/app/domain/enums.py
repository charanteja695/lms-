"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class ItemKind(StrEnum):
    # self-declared by the student
    EDUCATION = "education"
    EXPERIENCE = "experience"
    PROJECT = "project"
    SKILL = "skill"
    ACHIEVEMENT = "achievement"
    # created by this service from platform events; verified, read-only
    CERTIFICATE = "certificate"
    COURSE = "course"
    SKILL_SCORE = "skill_score"


SELF_KINDS = (ItemKind.EDUCATION, ItemKind.EXPERIENCE, ItemKind.PROJECT, ItemKind.SKILL, ItemKind.ACHIEVEMENT)
VERIFIED_KINDS = (ItemKind.CERTIFICATE, ItemKind.COURSE, ItemKind.SKILL_SCORE)


class ItemSource(StrEnum):
    SELF = "self"
    CERTIFICATE = "certificate-service"
    ASSESSMENT = "assessment-service"


class VersionSource(StrEnum):
    MANUAL = "manual"
    AI = "ai"  # saved automatically before a suggestion was applied
    RESTORE = "restore"


class ExperienceLevel(StrEnum):
    """How much work experience the resume's owner has; it decides the section order and the length a resume should be."""

    FRESHER = "fresher"  # students and graduates: internships count as experience
    JUNIOR = "junior"  # 1–3 years
    MID = "mid"  # 3–8 years
    SENIOR = "senior"  # 8+ years


class SectionKey(StrEnum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECTS = "projects"
    SKILLS = "skills"
    CERTIFICATES = "certificates"
    COURSES = "courses"
    SKILL_SCORES = "skill_scores"
    ACHIEVEMENTS = "achievements"


# which profile items feed which resume section
SECTION_KINDS: dict[SectionKey, ItemKind] = {
    SectionKey.EXPERIENCE: ItemKind.EXPERIENCE,
    SectionKey.EDUCATION: ItemKind.EDUCATION,
    SectionKey.PROJECTS: ItemKind.PROJECT,
    SectionKey.SKILLS: ItemKind.SKILL,
    SectionKey.CERTIFICATES: ItemKind.CERTIFICATE,
    SectionKey.COURSES: ItemKind.COURSE,
    SectionKey.SKILL_SCORES: ItemKind.SKILL_SCORE,
    SectionKey.ACHIEVEMENTS: ItemKind.ACHIEVEMENT,
}

# ATS-friendly headings (docs/PRODUCT.md §5.6): standard words a parser recognises
DEFAULT_TITLES: dict[SectionKey, str] = {
    SectionKey.SUMMARY: "Summary",
    SectionKey.EXPERIENCE: "Experience",
    SectionKey.EDUCATION: "Education",
    SectionKey.PROJECTS: "Projects",
    SectionKey.SKILLS: "Skills",
    SectionKey.CERTIFICATES: "Certifications",
    SectionKey.COURSES: "Courses completed",
    SectionKey.SKILL_SCORES: "Assessment scores",
    SectionKey.ACHIEVEMENTS: "Achievements",
}
