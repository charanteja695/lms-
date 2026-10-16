"""The permission catalog: every feature a person can be allowed (1) or not (0), in one table.

A person's effective permissions = their role's defaults (editable by a super admin, see ``RolePermission``)
+ an admin's assigned scopes (the platform permissions below) + per-person grants − per-person removals
(``UserPermission``). They are carried in the access token's ``scopes`` claim, which every service checks
(``AccessTokenClaims.can`` / ``has_scope``). A super admin holds everything and cannot be restricted.

What a permission lets you *do* is decided here; *whose data* you reach is not: an organisation member acts within
their own organisation, platform staff across the platform (each service's own rule). So granting
"grade attempts" to a staff member lets them grade their own institution's students, never another's.

``audience`` says who may hold a permission at all, so a person grant can never put a platform-wide power on an
organisation member (or an organisation's role on platform staff):
  platform     admins only (these are the admin scopes)
  institution  institution members (head, staff, student)
  employer     employer members (employer admin, recruiter)
  member       any organisation member
"""

from dataclasses import dataclass
from typing import Literal

from app.permissions.roles import ADMIN_SCOPES, AdminScope, Role

Audience = Literal["platform", "institution", "employer", "member"]

_S, _ST, _H = Role.STUDENT, Role.STAFF, Role.INSTITUTION_HEAD
_EA, _R = Role.EMPLOYER_ADMIN, Role.RECRUITER


@dataclass(frozen=True, slots=True)
class Permission:
    key: str
    label: str
    description: str
    modules: tuple[str, ...]  # the menu modules (``permissions.sections``) holding it opens
    audience: Audience
    default_roles: frozenset[Role] = frozenset()


def _p(
    key: str | AdminScope, label: str, description: str, modules: tuple[str, ...], audience: Audience, *roles: Role
) -> Permission:
    return Permission(str(key), label, description, modules, audience, frozenset(roles))


PERMISSIONS: tuple[Permission, ...] = (
    # ---------------------------------------------------------------- platform (admin scopes)
    _p(
        AdminScope.ACCOUNTS_MANAGE,
        "Institutions and their people",
        "Own institutions and their members; every institution's batches, course requests and subscriptions.",
        ("subscriptions", "learning"),
        "platform",
    ),
    _p(
        AdminScope.CAREERS_MANAGE,
        "Careers and hiring",
        "Own employers and recruiters; verify companies, approve jobs; every student's career profile; practice interview plans.",
        ("career", "job_portal", "ai_interview", "analytics"),
        "platform",
    ),
    _p(
        AdminScope.CONTENT_AUTHOR,
        "Write courses and questions",
        "Write courses, coding problems, questions, tests, certificate templates and the tutor FAQ.",
        ("catalog", "code_execution", "assessments", "certificates", "ai_tutor"),
        "platform",
    ),
    _p(
        AdminScope.CONTENT_REVIEW,
        "Review and publish content",
        "Approve or reject what authors wrote, and publish it.",
        ("catalog", "code_execution", "assessments", "certificates", "analytics"),
        "platform",
    ),
    _p(
        AdminScope.EXAMS_MANAGE,
        "Exams and integrity",
        "Schedule exams, grade any attempt, decide integrity cases and appeals.",
        ("assessments", "proctoring", "certificates", "support", "analytics"),
        "platform",
    ),
    _p(
        AdminScope.SUPPORT_MANAGE,
        "Support",
        "Every support queue, SLA policies, tutor escalations.",
        ("support", "ai_tutor", "analytics"),
        "platform",
    ),
    _p(
        AdminScope.AI_MANAGE,
        "AI settings",
        "Models, prompts, quotas and the tutor's search index.",
        ("ai_tutor", "analytics", "ai_gateway"),
        "platform",
    ),
    _p(
        AdminScope.ANALYTICS_VIEW,
        "Platform-wide analytics",
        "Every analytics dashboard, across the platform.",
        ("analytics",),
        "platform",
    ),
    _p(
        AdminScope.BILLING_MANAGE,
        "Billing",
        "Prices, quotes, every organisation's invoices, payments and credit notes.",
        ("billing", "analytics"),
        "platform",
    ),
    # ---------------------------------------------------------------- learning
    _p(
        "catalog.read",
        "Read course content",
        "Open the courses their institution has.",
        ("catalog",),
        "institution",
        _S,
        _ST,
        _H,
    ),
    _p(
        "catalog.browse",
        "Browse the course catalogue",
        "See every course and learning path to plan or request them.",
        ("catalog",),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "academics.view",
        "See the academic structure",
        "Their institution's departments, programs, sections and who is in each.",
        (),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "academics.manage",
        "Keep the academic structure",
        "Create and change departments (and their heads), programs and sections, and place students in sections.",
        (),
        "institution",
        _H,
    ),
    _p("learning.study", "Study", "Their own enrolments, lessons and progress.", ("learning",), "institution", _S),
    _p(
        "learning.batches.view",
        "See batches",
        "Their institution's batches and who is in them.",
        ("learning",),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "learning.batches.manage",
        "Manage batches",
        "Create batches and enrol or remove students.",
        ("learning",),
        "institution",
        _H,
    ),
    _p(
        "subscriptions.request",
        "Course requests and subscriptions",
        "Ask for courses and see the institution's subscriptions.",
        ("subscriptions",),
        "institution",
        _H,
    ),
    _p(
        "code.practice",
        "Coding practice",
        "Solve problems and use the compiler.",
        ("code_execution",),
        "institution",
        _S,
        _ST,
        _H,
    ),
    _p(
        "code.submissions",
        "Own code submissions",
        "Their own submissions and results.",
        ("code_execution",),
        "institution",
        _S,
    ),
    _p("tutor.chat", "Use the AI tutor", "Ask the tutor about their lessons.", ("ai_tutor",), "institution", _S),
    _p(
        "tutor.faq.manage",
        "Institution tutor FAQ",
        "Write the FAQ answers the tutor gives their institution.",
        ("ai_tutor",),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "tutor.conversations.view",
        "Read students' tutor chats",
        "Read their own students' tutor conversations (to promote good answers).",
        ("ai_tutor",),
        "institution",
        _ST,
        _H,
    ),
    # ---------------------------------------------------------------- exams
    _p(
        "assessments.take",
        "Take tests",
        "Take the tests scheduled for them and see their results.",
        ("assessments",),
        "institution",
        _S,
    ),
    _p(
        "assessments.grade",
        "Grade and supervise attempts",
        "Grade, pause or stop their own students' test attempts.",
        ("assessments",),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "assessments.author",
        "Write hiring questions and tests",
        "Write their company's own questions and hiring tests.",
        ("assessments",),
        "employer",
        _EA,
        _R,
    ),
    _p(
        "assessments.review",
        "Approve hiring questions and tests",
        "Approve their company's questions and tests.",
        ("assessments",),
        "employer",
        _EA,
    ),
    _p(
        "assessments.manage",
        "Run hiring tests",
        "Schedule their company's tests, invite candidates and release results.",
        ("assessments",),
        "employer",
        _EA,
        _R,
    ),
    _p(
        "proctoring.take",
        "Proctored exams",
        "Sit proctored exams and see their own integrity reviews and appeals.",
        ("proctoring",),
        "institution",
        _S,
    ),
    _p(
        "proctoring.monitor",
        "Watch proctored exams",
        "Watch and act on their own organisation's live proctored sessions and cases.",
        ("proctoring",),
        "member",
        _ST,
        _H,
        _EA,
        _R,
    ),
    _p("certificates.own", "Own certificates", "Their own certificates.", ("certificates",), "institution", _S),
    _p(
        "certificates.students",
        "Students' certificates",
        "Their own institution's students' certificates.",
        ("certificates",),
        "institution",
        _ST,
        _H,
    ),
    # ---------------------------------------------------------------- careers
    _p(
        "career.profile",
        "Career profile and resumes",
        "Their own skills profile and resumes.",
        ("career",),
        "institution",
        _S,
    ),
    _p(
        "career.students",
        "Students' career profiles",
        "Their own institution's students' profiles and resumes.",
        ("career",),
        "institution",
        _ST,
        _H,
    ),
    _p("jobs.apply", "Apply for jobs", "Search jobs and apply.", ("job_portal",), "institution", _S),
    _p(
        "jobs.placements",
        "Placements",
        "Their institution's students' applications and placements, and placement drives.",
        ("job_portal",),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "jobs.drives.propose",
        "Propose placement drives",
        "Invite companies to recruit at the institution.",
        ("job_portal",),
        "institution",
        _H,
    ),
    _p(
        "jobs.hire",
        "Hiring",
        "Post their company's jobs and move applicants through the pipeline.",
        ("job_portal",),
        "employer",
        _EA,
        _R,
    ),
    _p(
        "jobs.company.manage",
        "Company profile and drives",
        "Edit the company profile and accept or decline placement drives.",
        ("job_portal",),
        "employer",
        _EA,
    ),
    _p(
        "interviews.practice",
        "Practice interviews",
        "Take AI practice and screening interviews.",
        ("ai_interview",),
        "institution",
        _S,
    ),
    _p(
        "interviews.screen",
        "Screening interviews",
        "Write screening plans and review their company's AI interviews.",
        ("ai_interview",),
        "employer",
        _EA,
        _R,
    ),
    # ---------------------------------------------------------------- organisation
    _p(
        "analytics.own",
        "Own organisation's analytics",
        "Dashboards and reports for their own organisation.",
        ("analytics",),
        "member",
        _ST,
        _H,
        _EA,
        _R,
    ),
    _p(
        "billing.contact",
        "Organisation billing",
        "Their organisation's billing profile, invoices and payments.",
        ("billing",),
        "member",
        _H,
        _EA,
    ),
    _p("billing.plans.buy", "Buy hiring plans", "Buy job-post plans for their company.", ("billing",), "employer", _EA),
    _p("support.ask", "Ask for help", "Open support tickets.", ("support",), "institution", _S),
    _p(
        "support.agent",
        "Answer support tickets",
        "Answer their institution's support queue.",
        ("support",),
        "institution",
        _ST,
        _H,
    ),
    _p(
        "support.assign",
        "Assign support tickets",
        "Assign their queue's tickets to colleagues.",
        ("support",),
        "institution",
        _H,
    ),
    _p(
        "ai.usage.own",
        "Own AI usage",
        "Their institution's AI usage and spend.",
        ("ai_gateway",),
        "institution",
        _ST,
        _H,
    ),
)

BY_KEY: dict[str, Permission] = {p.key: p for p in PERMISSIONS}
PLATFORM_KEYS: frozenset[str] = frozenset(p.key for p in PERMISSIONS if p.audience == "platform")

# Menu entries (feature level) → the permissions that open them (any one is enough). Display order.
MENU: dict[str, tuple[str, ...]] = {
    "my_learning": ("learning.study",),
    "batches": ("learning.batches.view", "learning.batches.manage", AdminScope.ACCOUNTS_MANAGE),
    "courses": ("catalog.browse", AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW),
    "learning_paths": ("catalog.browse", AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW),
    "course_requests": ("subscriptions.request", AdminScope.ACCOUNTS_MANAGE),
    "subscriptions": ("subscriptions.request", AdminScope.ACCOUNTS_MANAGE),
    "problems": ("code.practice", AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW),
    "compiler": ("code.practice", AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW),
    "my_submissions": ("code.submissions",),
    "ai_tutor": (
        "tutor.chat",
        "tutor.faq.manage",
        AdminScope.CONTENT_AUTHOR,
        AdminScope.SUPPORT_MANAGE,
        AdminScope.AI_MANAGE,
    ),
    "my_tests": ("assessments.take",),
    "question_bank": ("assessments.author", "assessments.review", AdminScope.CONTENT_AUTHOR, AdminScope.CONTENT_REVIEW),
    "tests": (
        "assessments.author",
        "assessments.manage",
        AdminScope.CONTENT_AUTHOR,
        AdminScope.CONTENT_REVIEW,
        AdminScope.EXAMS_MANAGE,
    ),
    "attempts": ("assessments.grade", "assessments.manage", AdminScope.EXAMS_MANAGE),
    "grading": ("assessments.grade", AdminScope.EXAMS_MANAGE),
    "my_integrity_cases": ("proctoring.take",),
    "proctoring": ("proctoring.monitor", AdminScope.EXAMS_MANAGE),
    "certificates": (
        "certificates.own",
        "certificates.students",
        AdminScope.CONTENT_AUTHOR,
        AdminScope.CONTENT_REVIEW,
        AdminScope.EXAMS_MANAGE,
    ),
    "support": ("support.ask", "support.agent", AdminScope.EXAMS_MANAGE, AdminScope.SUPPORT_MANAGE),
    "career": ("career.profile", "career.students", AdminScope.CAREERS_MANAGE),
    "jobs": ("jobs.apply", "jobs.placements", "jobs.hire", AdminScope.CAREERS_MANAGE),
    "ai_interviews": ("interviews.practice", "interviews.screen", AdminScope.CAREERS_MANAGE),
    "analytics": (
        "analytics.own",
        AdminScope.CONTENT_REVIEW,
        AdminScope.EXAMS_MANAGE,
        AdminScope.SUPPORT_MANAGE,
        AdminScope.CAREERS_MANAGE,
        AdminScope.AI_MANAGE,
        AdminScope.BILLING_MANAGE,
        AdminScope.ANALYTICS_VIEW,
    ),
    "billing": ("billing.contact", AdminScope.BILLING_MANAGE),
    "ai_settings": (AdminScope.AI_MANAGE, "ai.usage.own"),
}

# The other services' modules, in menu order (``permissions.sections``); "notifications" is everyone's.
MODULES: tuple[str, ...] = (
    "catalog",
    "subscriptions",
    "learning",
    "code_execution",
    "assessments",
    "proctoring",
    "certificates",
    "ai_tutor",
    "support",
    "career",
    "job_portal",
    "ai_interview",
    "notifications",
    "analytics",
    "billing",
    "ai_gateway",
)


def eligible(permission: Permission, role: Role, organization_type: str | None) -> bool:
    """Whether someone with this role (and organisation kind) may hold ``permission`` at all."""
    if permission.audience == "platform":
        return role == Role.SUPER_ADMIN or (role == Role.ADMIN and permission.key in ADMIN_SCOPES)
    if role in (Role.ADMIN, Role.SUPER_ADMIN):
        return False
    if permission.audience == "member":
        return True
    return permission.audience == organization_type
