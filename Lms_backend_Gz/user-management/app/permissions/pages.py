"""The permission matrix: every page a person can open, and the actions they may take on it.

Each cell is one permission key, ``<page>.<action>`` (``students.delete``, ``batches.create``). A super admin ticks
cells per role and per person. A cell implies the older, coarser feature keys the other services check
(``batches.create`` → ``learning.batches.manage``), so every service keeps working while it moves to checking the
cells themselves. A page's other actions only count while its View is held: no View, no page.
"""

from dataclasses import dataclass, field

from app.permissions.roles import Role

ACTIONS: tuple[str, ...] = ("view", "create", "update", "delete", "revoke", "export", "approve")
ACTION_LABELS: dict[str, str] = {
    "view": "View",
    "create": "Create",
    "update": "Update",
    "delete": "Delete",
    "revoke": "Revoke",
    "export": "Export",
    "approve": "Approve",
}

_A, _H, _S, _L = Role.ADMIN, Role.INSTITUTION_HEAD, Role.STAFF, Role.STUDENT


@dataclass(frozen=True, slots=True)
class Page:
    key: str
    label: str
    group: str
    description: str
    holders: frozenset[Role]  # who may ever be given anything on this page
    # action -> roles that have it by default
    defaults: dict[str, frozenset[Role]]
    # action -> what each action means here (shown as the cell's tooltip)
    meaning: dict[str, str] = field(default_factory=dict)
    # action -> older feature keys the action implies (what other services still check)
    implies: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def actions(self) -> tuple[str, ...]:
        return tuple(a for a in ACTIONS if a in self.defaults)


def _page(
    key: str,
    label: str,
    group: str,
    description: str,
    holders: tuple[Role, ...],
    actions: dict[str, tuple[tuple[Role, ...], str, tuple[str, ...]]],
) -> Page:
    """``actions``: action -> (roles holding it by default, what it means here, the older keys it implies)."""
    return Page(
        key,
        label,
        group,
        description,
        frozenset(holders),
        defaults={a: frozenset(v[0]) for a, v in actions.items()},
        meaning={a: v[1] for a, v in actions.items()},
        implies={a: v[2] for a, v in actions.items()},
    )


PEOPLE = "User management"
LEARN = "Learning"
PRACTICE = "Practice & AI tutor"
EXAMS = "Exams & certificates"
CAREER = "Career & placements"
SUPPORT = "Support & reports"

PAGES: tuple[Page, ...] = (
    # ---------------------------------------------------------------- people
    _page(
        "institutions",
        "Institutions",
        PEOPLE,
        "Colleges and schools the admin owns.",
        (_A,),
        {
            "view": ((_A,), "See their institutions", ()),
            "create": ((_A,), "Add an institution", ()),
            "update": ((_A,), "Edit an institution's details", ()),
            "delete": ((_A,), "Delete an institution", ()),
            "revoke": ((_A,), "Suspend or reactivate an institution, sign its people out", ()),
            "export": ((_A,), "Download the list", ()),
        },
    ),
    _page(
        "institution_heads",
        "Institution heads",
        PEOPLE,
        "The person who runs each institution.",
        (_A,),
        {
            "view": ((_A,), "See institution heads", ()),
            "create": ((_A,), "Add an institution head", ()),
            "update": ((_A,), "Edit their details", ()),
            "delete": ((_A,), "Delete an institution head", ()),
            "revoke": ((_A,), "Suspend, reactivate or sign out", ()),
            "export": ((_A,), "Download the list", ()),
        },
    ),
    _page(
        "staff",
        "Staff",
        PEOPLE,
        "Teachers and staff.",
        (_A, _H),
        {
            "view": ((_A, _H), "See staff", ()),
            "create": ((_A, _H), "Add a staff member", ()),
            "update": ((_A, _H), "Edit their details", ()),
            "delete": ((_A, _H), "Delete a staff member", ()),
            "revoke": ((_A, _H), "Suspend, reactivate or sign out", ()),
            "export": ((_A, _H), "Download the list", ()),
        },
    ),
    _page(
        "students",
        "Students",
        PEOPLE,
        "Learners.",
        (_A, _H, _S),
        {
            "view": ((_A, _H, _S), "See students", ()),
            "create": ((_A, _H, _S), "Add a student", ()),
            "update": ((_A, _H, _S), "Edit their details", ()),
            "delete": ((_A, _H), "Delete a student", ()),
            "revoke": ((_A, _H), "Suspend, reactivate or sign out", ()),
            "export": ((_A, _H), "Download the list", ()),
        },
    ),
    _page(
        "academic_structure",
        "Academic structure",
        PEOPLE,
        "Departments, programs and sections.",
        (_H, _S),
        {
            "view": ((_H, _S), "See departments, programs and sections", ("academics.view",)),
            "create": ((_H,), "Add a department, program or section", ("academics.manage",)),
            "update": ((_H,), "Edit them and place students in sections", ("academics.manage",)),
            "delete": ((_H,), "Delete them", ("academics.manage",)),
        },
    ),
    # ---------------------------------------------------------------- learning
    _page(
        "my_learning",
        "My learning",
        LEARN,
        "Their own courses, lessons and progress.",
        (_L,),
        {
            "view": ((_L,), "Study their courses", ("learning.study", "catalog.read")),
        },
    ),
    _page(
        "courses",
        "Courses",
        LEARN,
        "The course catalogue.",
        (_H, _S),
        {
            "view": ((_H, _S), "Browse every course and learning path", ("catalog.browse", "catalog.read")),
        },
    ),
    _page(
        "batches",
        "Batches",
        LEARN,
        "Student cohorts on a course.",
        (_H, _S),
        {
            "view": ((_H, _S), "See batches and who is in them", ("learning.batches.view",)),
            "create": ((_H,), "Create a batch, enrol students", ("learning.batches.manage",)),
            "revoke": ((_H,), "Remove a student from a batch", ("learning.batches.manage",)),
        },
    ),
    _page(
        "course_requests",
        "Course requests",
        LEARN,
        "Ask for courses; the institution's subscriptions.",
        (_H,),
        {
            "view": ((_H,), "See requests and subscriptions", ("subscriptions.request",)),
            "create": ((_H,), "Request a course", ("subscriptions.request",)),
        },
    ),
    # ---------------------------------------------------------------- practice
    _page(
        "coding_practice",
        "Coding practice",
        PRACTICE,
        "Problems and the compiler.",
        (_H, _S, _L),
        {
            "view": ((_H, _S, _L), "Solve problems and use the compiler", ("code.practice",)),
        },
    ),
    _page(
        "my_submissions",
        "My submissions",
        PRACTICE,
        "Their own code submissions.",
        (_L,),
        {
            "view": ((_L,), "See their submissions and results", ("code.submissions",)),
        },
    ),
    _page(
        "ai_tutor",
        "AI tutor",
        PRACTICE,
        "Ask the tutor about lessons.",
        (_L,),
        {
            "view": ((_L,), "Chat with the AI tutor", ("tutor.chat",)),
        },
    ),
    _page(
        "tutor_faq",
        "Tutor FAQ",
        PRACTICE,
        "Answers the tutor gives the institution.",
        (_H, _S),
        {
            "view": ((_H, _S), "See the FAQ", ("tutor.faq.manage",)),
            "create": ((_H, _S), "Write an answer", ("tutor.faq.manage",)),
            "update": ((_H, _S), "Edit an answer", ("tutor.faq.manage",)),
            "delete": ((_H, _S), "Delete an answer", ("tutor.faq.manage",)),
        },
    ),
    _page(
        "tutor_chats",
        "Students' tutor chats",
        PRACTICE,
        "Their students' tutor conversations.",
        (_H, _S),
        {
            "view": ((_H, _S), "Read conversations to promote good answers", ("tutor.conversations.view",)),
        },
    ),
    # ---------------------------------------------------------------- exams
    _page(
        "my_tests",
        "My tests",
        EXAMS,
        "Tests scheduled for them.",
        (_L,),
        {
            "view": ((_L,), "Take tests and see results", ("assessments.take",)),
        },
    ),
    _page(
        "attempts",
        "Attempts & grading",
        EXAMS,
        "Their students' test attempts.",
        (_H, _S),
        {
            "view": ((_H, _S), "See attempts", ("assessments.grade",)),
            "update": ((_H, _S), "Grade, pause or stop an attempt", ("assessments.grade",)),
        },
    ),
    _page(
        "exam_reviews",
        "Exam reviews",
        EXAMS,
        "Integrity reviews of their own exams.",
        (_L,),
        {
            "view": ((_L,), "Sit proctored exams, see reviews", ("proctoring.take",)),
            "create": ((_L,), "Appeal a decision", ("proctoring.take",)),
        },
    ),
    _page(
        "proctoring",
        "Live proctoring",
        EXAMS,
        "Their students' live proctored exams.",
        (_H, _S),
        {
            "view": ((_H, _S), "Watch live exams and cases", ("proctoring.monitor",)),
            "update": ((_H, _S), "Warn, pause or stop a session", ("proctoring.monitor",)),
        },
    ),
    _page(
        "my_certificates",
        "My certificates",
        EXAMS,
        "Their own certificates.",
        (_L,),
        {
            "view": ((_L,), "See their certificates", ("certificates.own",)),
            "export": ((_L,), "Download and share", ("certificates.own",)),
        },
    ),
    _page(
        "certificates",
        "Certificates",
        EXAMS,
        "Their students' certificates.",
        (_H, _S),
        {
            "view": ((_H, _S), "See students' certificates", ("certificates.students",)),
            "export": ((_H, _S), "Download the list", ("certificates.students",)),
        },
    ),
    # ---------------------------------------------------------------- career
    _page(
        "my_career",
        "Resumes & profile",
        CAREER,
        "Their own skill profile and resumes.",
        (_L,),
        {
            "view": ((_L,), "See their profile and resumes", ("career.profile",)),
            "create": ((_L,), "Add entries, create resumes", ("career.profile",)),
            "update": ((_L,), "Edit them", ("career.profile",)),
            "delete": ((_L,), "Delete them", ("career.profile",)),
        },
    ),
    _page(
        "student_profiles",
        "Student profiles",
        CAREER,
        "Their students' profiles and resumes.",
        (_H, _S),
        {
            "view": ((_H, _S), "Read a student's profile", ("career.students",)),
        },
    ),
    _page(
        "jobs",
        "Jobs",
        CAREER,
        "Job openings for students.",
        (_L,),
        {
            "view": ((_L,), "Search jobs", ("jobs.apply",)),
            "create": ((_L,), "Apply", ("jobs.apply",)),
            "revoke": ((_L,), "Withdraw an application", ("jobs.apply",)),
        },
    ),
    _page(
        "placements",
        "Placements",
        CAREER,
        "Students' applications, offers and placement drives.",
        (_H, _S),
        {
            "view": ((_H, _S), "See applications and placements", ("jobs.placements",)),
            "create": ((_H,), "Propose a placement drive", ("jobs.drives.propose",)),
        },
    ),
    _page(
        "ai_interview",
        "AI interview",
        CAREER,
        "Practice and company interviews.",
        (_L,),
        {
            "view": ((_L,), "See interviews and reports", ("interviews.practice",)),
            "create": ((_L,), "Start an interview", ("interviews.practice",)),
        },
    ),
    # ---------------------------------------------------------------- support and reports
    _page(
        "support",
        "Help",
        SUPPORT,
        "Their own support tickets.",
        (_L,),
        {
            "view": ((_L,), "See their tickets", ("support.ask",)),
            "create": ((_L,), "Open a ticket", ("support.ask",)),
        },
    ),
    _page(
        "support_queue",
        "Support queue",
        SUPPORT,
        "The institution's support tickets.",
        (_H, _S),
        {
            "view": ((_H, _S), "See the queue", ("support.agent",)),
            "update": ((_H, _S), "Answer and close tickets", ("support.agent",)),
            "approve": ((_H,), "Assign tickets to colleagues", ("support.assign",)),
        },
    ),
    _page(
        "reports",
        "Reports",
        SUPPORT,
        "The organisation's dashboards.",
        (_H, _S),
        {
            "view": ((_H, _S), "See dashboards", ("analytics.own",)),
            "export": ((_H, _S), "Download reports", ("analytics.own",)),
        },
    ),
    _page(
        "billing",
        "Billing",
        SUPPORT,
        "The organisation's billing profile and invoices.",
        (_H,),
        {
            "view": ((_H,), "See invoices", ("billing.contact",)),
            "update": ((_H,), "Edit the billing profile, pay", ("billing.contact",)),
        },
    ),
    _page(
        "ai_usage",
        "AI usage",
        SUPPORT,
        "The institution's AI usage and spend.",
        (_H, _S),
        {
            "view": ((_H, _S), "See AI usage", ("ai.usage.own",)),
        },
    ),
)

PAGE_BY_KEY: dict[str, Page] = {p.key: p for p in PAGES}
CELL_KEYS: frozenset[str] = frozenset(f"{p.key}.{a}" for p in PAGES for a in p.actions)
# Roles whose access is set on the matrix (an admin's platform scopes are set on their own page).
MATRIX_ROLES: tuple[Role, ...] = (_A, _H, _S, _L)


def split(cell: str) -> tuple[Page, str] | None:
    page_key, _, action = cell.rpartition(".")
    page = PAGE_BY_KEY.get(page_key)
    return (page, action) if page is not None and action in page.defaults else None


def cell_defaults(role: Role) -> set[str]:
    return {f"{p.key}.{a}" for p in PAGES for a, roles in p.defaults.items() if role in roles}


def may_hold(cell: str, role: Role) -> bool:
    found = split(cell)
    return found is not None and role in found[0].holders


def without_orphans(cells: set[str]) -> set[str]:
    """A page's other actions only count while its View is held."""
    return {
        c for c in cells if (found := split(c)) is not None and (found[1] == "view" or f"{found[0].key}.view" in cells)
    }


def implied(cells: set[str]) -> set[str]:
    """The older feature keys these cells imply (what the other services check until they read cells)."""
    out: set[str] = set()
    for cell in cells:
        found = split(cell)
        if found:
            out.update(found[0].implies.get(found[1], ()))
    return out


# user-management's own pages: a target role's page, and which cell each user action needs
PEOPLE_PAGE: dict[Role, str] = {
    Role.INSTITUTION_HEAD: "institution_heads",
    Role.STAFF: "staff",
    Role.STUDENT: "students",
}
