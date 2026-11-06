"""The choices offered when a student starts a resume, with the words that explain each. Kept here (not in the client) so the
rules they describe — section order, length — and the words that describe them change together."""

from app.domain.enums import ExperienceLevel

LEVEL_OPTIONS: list[dict[str, str]] = [
    {
        "key": ExperienceLevel.FRESHER.value, "label": "Fresher",
        "note": "Skills, projects and internships go first; education follows. One page.",
    },
    {
        "key": ExperienceLevel.JUNIOR.value, "label": "1–3 years",
        "note": "Work experience goes first, with projects right after. One page.",
    },
    {
        "key": ExperienceLevel.MID.value, "label": "3–8 years",
        "note": "Experience first, with results in numbers; education moves to the end. One to two pages.",
    },
    {
        "key": ExperienceLevel.SENIOR.value, "label": "8+ years",
        "note": "Recent roles in detail, a strong summary, education last. Up to two pages.",
    },
]

TONE_OPTIONS: list[dict[str, str]] = [
    {"key": "professional", "label": "Professional", "note": "Clear and formal"},
    {"key": "warm", "label": "Warm", "note": "Friendly, still professional"},
    {"key": "concise", "label": "Concise", "note": "As short as possible"},
]

START_OPTIONS: list[dict[str, object]] = [
    {"key": "profile", "label": "My profile", "description": "Your certificates, scores and entries, already filled in", "accepts": []},
    {"key": "import", "label": "Upload old resume", "description": "PDF or Word — we read it and you check each entry", "accepts": [".pdf", ".docx", ".txt"]},
    {"key": "linkedin", "label": "LinkedIn profile", "description": "On LinkedIn: More › Save to PDF, then upload that file", "accepts": [".pdf"]},
    {"key": "blank", "label": "Start empty", "description": "Pick each section yourself", "accepts": []},
]
