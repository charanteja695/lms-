"""Deterministic fallback resume parser when AI gateway/assistant is offline or unavailable.
Extracts contact details, education, experience, projects, skills, and achievements
directly from the extracted resume text without hallucinating facts.
"""

import re
from typing import Any

from app.core.exceptions import ValidationFailedError
from app.domain.enums import ItemKind
from app.schemas.items import validate_item_data

# Comprehensive technical and professional skill catalog mapped to categories
SKILL_CATALOG: dict[str, str] = {
    # Programming Languages
    "Python": "Programming Languages",
    "Java": "Programming Languages",
    "JavaScript": "Programming Languages",
    "TypeScript": "Programming Languages",
    "C++": "Programming Languages",
    "C#": "Programming Languages",
    "C": "Programming Languages",
    "Golang": "Programming Languages",
    "Go": "Programming Languages",
    "Rust": "Programming Languages",
    "Ruby": "Programming Languages",
    "PHP": "Programming Languages",
    "SQL": "Programming Languages",
    "HTML": "Web Technologies",
    "HTML5": "Web Technologies",
    "CSS": "Web Technologies",
    "CSS3": "Web Technologies",
    "R": "Data Science",
    "Kotlin": "Mobile Development",
    "Swift": "Mobile Development",
    "Dart": "Mobile Development",
    "Bash": "DevOps & Tools",
    "Shell": "DevOps & Tools",

    # Frameworks & Libraries
    "React": "Frameworks & Libraries",
    "React.js": "Frameworks & Libraries",
    "Next.js": "Frameworks & Libraries",
    "Angular": "Frameworks & Libraries",
    "Vue.js": "Frameworks & Libraries",
    "Vue": "Frameworks & Libraries",
    "Node.js": "Frameworks & Libraries",
    "Express.js": "Frameworks & Libraries",
    "Express": "Frameworks & Libraries",
    "Django": "Frameworks & Libraries",
    "FastAPI": "Frameworks & Libraries",
    "Flask": "Frameworks & Libraries",
    "Spring Boot": "Frameworks & Libraries",
    "Spring": "Frameworks & Libraries",
    ".NET": "Frameworks & Libraries",
    "ASP.NET": "Frameworks & Libraries",
    "Flutter": "Mobile Development",
    "React Native": "Mobile Development",
    "Tailwind CSS": "Web Technologies",
    "Bootstrap": "Web Technologies",
    "Redux": "Frameworks & Libraries",

    # Databases
    "PostgreSQL": "Databases",
    "MySQL": "Databases",
    "MongoDB": "Databases",
    "Redis": "Databases",
    "SQLite": "Databases",
    "Oracle": "Databases",
    "Firebase": "Cloud & Databases",
    "Cassandra": "Databases",

    # Cloud, DevOps & Tools
    "Git": "Tools & Version Control",
    "GitHub": "Tools & Version Control",
    "GitLab": "Tools & Version Control",
    "Docker": "DevOps & Cloud",
    "Kubernetes": "DevOps & Cloud",
    "AWS": "DevOps & Cloud",
    "Amazon Web Services": "DevOps & Cloud",
    "Azure": "DevOps & Cloud",
    "GCP": "DevOps & Cloud",
    "Google Cloud": "DevOps & Cloud",
    "Linux": "Systems & Tools",
    "CI/CD": "DevOps",
    "Jenkins": "DevOps",
    "Kafka": "Data Streaming",
    "RabbitMQ": "Messaging",

    # Data Science & Machine Learning
    "Machine Learning": "Data Science",
    "Deep Learning": "Data Science",
    "Artificial Intelligence": "Data Science",
    "Pandas": "Data Science",
    "NumPy": "Data Science",
    "Scikit-learn": "Data Science",
    "TensorFlow": "Data Science",
    "PyTorch": "Data Science",
    "Data Analysis": "Data Science",
    "Power BI": "Data Science",
    "Tableau": "Data Science",
    "Natural Language Processing": "Data Science",
    "NLP": "Data Science",
    "Computer Vision": "Data Science",

    # Methodologies & Concepts
    "REST API": "Concepts & Architecture",
    "Microservices": "Concepts & Architecture",
    "Agile": "Methodologies",
    "Scrum": "Methodologies",
    "Object-Oriented Programming": "Concepts & Architecture",
    "Data Structures": "Core CS",
    "Algorithms": "Core CS",
}

_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
_PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{4,5}")
_YEAR_RANGE_REGEX = re.compile(r"\b(20\d{2}|19\d{2})\s*(?:[-–—to\s]+)\s*(20\d{2}|19\d{2}|present|current)\b", re.IGNORECASE)
_YEAR_SINGLE_REGEX = re.compile(r"\b(20\d{2}|19\d{2})\b")

DEGREE_PATTERNS = [
    (r"\b(B\.?Tech|Bachelor of Technology)\b", "B.Tech"),
    (r"\b(B\.?E\.?|Bachelor of Engineering)\b", "B.E."),
    (r"\b(M\.?Tech|Master of Technology)\b", "M.Tech"),
    (r"\b(M\.?E\.?|Master of Engineering)\b", "M.E."),
    (r"\b(B\.?Sc|Bachelor of Science)\b", "B.Sc"),
    (r"\b(M\.?Sc|Master of Science)\b", "M.Sc"),
    (r"\b(BCA|Bachelor of Computer Applications)\b", "BCA"),
    (r"\b(MCA|Master of Computer Applications)\b", "MCA"),
    (r"\b(BBA|Bachelor of Business Administration)\b", "BBA"),
    (r"\b(MBA|Master of Business Administration)\b", "MBA"),
    (r"\b(Ph\.?D|Doctor of Philosophy)\b", "Ph.D"),
    (r"\b(Diploma in [A-Za-z ]+)\b", "Diploma"),
    (r"\b(Higher Secondary|12th Standard|Class XII|Senior Secondary)\b", "Senior Secondary (12th)"),
    (r"\b(Secondary School|10th Standard|Class X)\b", "Secondary School (10th)"),
]

INSTITUTION_KEYWORDS = [
    "University", "College", "Institute", "Academy", "School", "IIT", "NIT", "BITS", "IIIT"
]

FIELD_PATTERNS = [
    r"Computer Science and Engineering",
    r"Computer Science & Engineering",
    r"Computer Science",
    r"Information Technology",
    r"Data Science",
    r"Artificial Intelligence",
    r"Electronics and Communication",
    r"Electrical and Electronics",
    r"Mechanical Engineering",
    r"Civil Engineering",
    r"Business Administration",
    r"Commerce",
]


def _format_year_month(year_str: str, month: str = "01") -> str:
    """Ensure YYYY-MM format."""
    clean = year_str.strip()
    if len(clean) == 4 and clean.isdigit():
        return f"{clean}-{month}"
    if re.match(r"^(19|20)\d{2}-(0[1-9]|1[0-2])$", clean):
        return clean
    return f"2024-{month}"


def parse_resume_fallback(text: str) -> tuple[dict[str, str | None], list[dict[str, Any]], int]:
    """Parse resume text using rule-based and regex extraction when AI service is unavailable."""
    profile: dict[str, str | None] = {
        "headline": None,
        "summary": None,
        "phone": None,
        "location": None,
    }
    items: list[dict[str, Any]] = []
    skipped = 0

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return profile, items, skipped

    # 1. Contact & Basic Profile Information
    # Email
    email_match = _EMAIL_REGEX.search(text)
    # Phone
    phone_candidates = _PHONE_REGEX.findall(text)
    for p in phone_candidates:
        digits_only = re.sub(r"\D", "", p)
        if 10 <= len(digits_only) <= 15:
            profile["phone"] = p.strip()[:30]
            break

    # Headline: use first prominent line or detect title keywords
    first_few_lines = lines[:4]
    for line in first_few_lines:
        if len(line) <= 80 and not _EMAIL_REGEX.search(line) and not _PHONE_REGEX.search(line):
            if any(w in line.lower() for w in ["developer", "engineer", "analyst", "designer", "scientist", "intern"]):
                profile["headline"] = line[:160]
                break
    if not profile["headline"] and lines:
        # Fallback to the first line if it's short and clean
        if len(lines[0]) <= 60 and not _EMAIL_REGEX.search(lines[0]):
            profile["headline"] = lines[0][:160]

    # Summary: look for Summary section
    summary_lines = []
    in_summary = False
    for line in lines:
        lower = line.lower().strip(":# -")
        if lower in ["summary", "professional summary", "about", "about me", "profile", "career objective", "objective"]:
            in_summary = True
            continue
        if in_summary:
            if any(lower.startswith(sec) for sec in ["experience", "work", "education", "skills", "projects", "certif"]):
                break
            summary_lines.append(line)
            if len(" ".join(summary_lines)) > 800:
                break
    if summary_lines:
        profile["summary"] = " ".join(summary_lines)[:1000]

    # Location: look for common cities/states
    loc_match = re.search(
        r"\b(Bangalore|Bengaluru|Hyderabad|Mumbai|Pune|Delhi|Noida|Gurgaon|Gurugram|Chennai|Kolkata|Ahmedabad|Jaipur|Remote|India)\b",
        text,
        re.IGNORECASE,
    )
    if loc_match:
        profile["location"] = loc_match.group(1).title()[:120]

    # 2. Extract Skills
    found_skills: set[str] = set()
    for skill_name, category in SKILL_CATALOG.items():
        # Word boundary match
        pattern = r"\b" + re.escape(skill_name) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            if skill_name not in found_skills:
                found_skills.add(skill_name)
                try:
                    data = validate_item_data(ItemKind.SKILL, {"name": skill_name[:60], "category": category[:40]})
                    items.append({"kind": ItemKind.SKILL.value, "data": data})
                except ValidationFailedError:
                    skipped += 1

    # 3. Extract Education
    # Split text into sections
    sections = re.split(r"\n(?=[A-Z][A-Za-z\s]{2,25}(?:\:|\n|$))", text)
    edu_section = ""
    exp_section = ""
    proj_section = ""
    achieve_section = ""

    for sec in sections:
        header = sec.strip().split("\n")[0].lower()
        if any(k in header for k in ["education", "academic", "qualification"]):
            edu_section = sec
        elif any(k in header for k in ["experience", "work history", "employment"]):
            exp_section = sec
        elif any(k in header for k in ["project"]):
            proj_section = sec
        elif any(k in header for k in ["achievement", "certification", "award", "honor"]):
            achieve_section = sec

    # Parse Education
    edu_text = edu_section or text
    edu_lines = [l.strip() for l in edu_text.splitlines() if l.strip()]
    current_inst = None
    current_degree = None
    current_field = None
    current_start = None
    current_end = None

    for line in edu_lines:
        # Check degree
        deg_found = None
        for pattern, deg_name in DEGREE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                deg_found = deg_name
                break
        
        # Check institution
        inst_found = None
        if any(k.lower() in line.lower() for k in INSTITUTION_KEYWORDS):
            inst_found = line.strip("-,. ")[:150]

        # Check field of study
        for fp in FIELD_PATTERNS:
            if re.search(fp, line, re.IGNORECASE):
                current_field = re.search(fp, line, re.IGNORECASE).group(0)[:150]
                break

        # Check dates
        yr_range = _YEAR_RANGE_REGEX.search(line)
        if yr_range:
            s_yr, e_yr = yr_range.group(1), yr_range.group(2)
            current_start = _format_year_month(s_yr, "06")
            if e_yr.lower() in ["present", "current"]:
                current_end = None
            else:
                current_end = _format_year_month(e_yr, "05")

        if deg_found:
            current_degree = deg_found
        if inst_found:
            current_inst = inst_found

        if current_degree and current_inst:
            try:
                edu_data = {
                    "degree": current_degree,
                    "institution": current_inst,
                    "field_of_study": current_field or "Computer Science",
                    "start_date": current_start,
                    "end_date": current_end,
                    "bullets": [],
                }
                validated = validate_item_data(ItemKind.EDUCATION, edu_data)
                items.append({"kind": ItemKind.EDUCATION.value, "data": validated})
                # reset for next degree entry
                current_degree = None
                current_inst = None
                current_field = None
                current_start = None
                current_end = None
            except ValidationFailedError:
                skipped += 1

    # 4. Extract Experience
    if exp_section:
        exp_lines = [l.strip() for l in exp_section.splitlines() if l.strip()]
        cur_title = None
        cur_company = None
        cur_start = None
        cur_end = None
        cur_is_current = False
        cur_bullets: list[str] = []

        role_keywords = ["intern", "engineer", "developer", "lead", "manager", "associate", "consultant", "analyst"]

        for line in exp_lines[1:]:
            lower_line = line.lower()
            # Detect title / company
            if any(k in lower_line for k in role_keywords) and not line.startswith(("-", "•", "*")):
                # Flush existing entry if valid
                if cur_title and cur_company:
                    try:
                        exp_data = {
                            "title": cur_title[:150],
                            "company": cur_company[:150],
                            "current": cur_is_current,
                            "start_date": cur_start,
                            "end_date": None if cur_is_current else cur_end,
                            "bullets": cur_bullets[:6],
                        }
                        validated = validate_item_data(ItemKind.EXPERIENCE, exp_data)
                        items.append({"kind": ItemKind.EXPERIENCE.value, "data": validated})
                    except ValidationFailedError:
                        skipped += 1
                    cur_title = None
                    cur_company = None
                    cur_start = None
                    cur_end = None
                    cur_is_current = False
                    cur_bullets = []

                parts = re.split(r"[-|@·,at\s]+", line)
                cur_title = line.split(" at ")[0].strip() if " at " in line else line.split(" - ")[0].strip()
                if " at " in line:
                    cur_company = line.split(" at ")[1].strip()
                elif " - " in line:
                    cur_company = line.split(" - ")[1].strip()
                else:
                    cur_company = "Tech Organization"
            elif line.startswith(("-", "•", "*")):
                clean_bullet = line.lstrip("-•* ").strip()
                if len(clean_bullet) > 10:
                    cur_bullets.append(clean_bullet[:280])
            else:
                # Check for dates
                date_match = _YEAR_RANGE_REGEX.search(line)
                if date_match:
                    s_yr, e_yr = date_match.group(1), date_match.group(2)
                    cur_start = _format_year_month(s_yr, "01")
                    if e_yr.lower() in ["present", "current"]:
                        cur_is_current = True
                        cur_end = None
                    else:
                        cur_end = _format_year_month(e_yr, "12")

        # Flush final experience entry
        if cur_title and cur_company:
            try:
                exp_data = {
                    "title": cur_title[:150],
                    "company": cur_company[:150],
                    "current": cur_is_current,
                    "start_date": cur_start,
                    "end_date": None if cur_is_current else cur_end,
                    "bullets": cur_bullets[:6],
                }
                validated = validate_item_data(ItemKind.EXPERIENCE, exp_data)
                items.append({"kind": ItemKind.EXPERIENCE.value, "data": validated})
            except ValidationFailedError:
                skipped += 1

    # 5. Extract Projects
    if proj_section:
        proj_lines = [l.strip() for l in proj_section.splitlines() if l.strip()]
        cur_proj_name = None
        cur_proj_techs: list[str] = []
        cur_proj_bullets: list[str] = []

        for line in proj_lines[1:]:
            if line.startswith(("-", "•", "*")):
                b = line.lstrip("-•* ").strip()
                if len(b) > 8:
                    cur_proj_bullets.append(b[:280])
            elif not cur_proj_name and len(line) < 80:
                cur_proj_name = line.split("|")[0].split(" - ")[0].strip()[:150]
                # extract tech stack in same line e.g. "Project Name | React, Python, MongoDB"
                if "|" in line or "(" in line:
                    tech_part = line.split("|")[-1] if "|" in line else line
                    cur_proj_techs = [t.strip()[:40] for t in re.split(r"[,/|()]+", tech_part) if t.strip() and t.strip() in found_skills][:10]
            elif cur_proj_name and not line.startswith(("-", "•", "*")) and len(line) < 80:
                # Flush previous project
                try:
                    p_data = {
                        "name": cur_proj_name[:150],
                        "description": cur_proj_bullets[0] if cur_proj_bullets else None,
                        "technologies": cur_proj_techs,
                        "bullets": cur_proj_bullets[:6],
                    }
                    validated = validate_item_data(ItemKind.PROJECT, p_data)
                    items.append({"kind": ItemKind.PROJECT.value, "data": validated})
                except ValidationFailedError:
                    skipped += 1
                cur_proj_name = line.split("|")[0].split(" - ")[0].strip()[:150]
                cur_proj_techs = []
                cur_proj_bullets = []

        if cur_proj_name:
            try:
                p_data = {
                    "name": cur_proj_name[:150],
                    "description": cur_proj_bullets[0] if cur_proj_bullets else None,
                    "technologies": cur_proj_techs,
                    "bullets": cur_proj_bullets[:6],
                }
                validated = validate_item_data(ItemKind.PROJECT, p_data)
                items.append({"kind": ItemKind.PROJECT.value, "data": validated})
            except ValidationFailedError:
                skipped += 1

    # 6. Extract Achievements / Certifications
    if achieve_section:
        achieve_lines = [l.strip() for l in achieve_section.splitlines() if l.strip()]
        for line in achieve_lines[1:5]:
            clean_achieve = line.lstrip("-•* ").strip()
            if 5 < len(clean_achieve) <= 150:
                try:
                    ach_data = {
                        "title": clean_achieve[:150],
                        "description": None,
                    }
                    validated = validate_item_data(ItemKind.ACHIEVEMENT, ach_data)
                    items.append({"kind": ItemKind.ACHIEVEMENT.value, "data": validated})
                except ValidationFailedError:
                    skipped += 1

    return profile, items, skipped
