"""AI assistance for a resume, through ai-gateway. Every result is a *suggestion* checked against the facts it came from
(app/ai/guard.py); nothing is saved from here. A suggestion that contains anything not in its source is returned with
``applicable: false`` and the list of what was invented, so the client can show it but not offer to apply it."""

import json
import re
from typing import Any

from app.ai.guard import Finding, invented, unsupported_keywords
from app.ats import keywords as kw
from app.ats.language import check_text
from app.clients.gateway import GatewayClient, GatewayDisabled, GatewayError, GatewayQuotaExceeded
from app.core.config import Settings
from app.core.exceptions import AiDisabledError, AiQuotaExceededError, AiUnavailableError, ValidationFailedError
from app.domain.enums import SELF_KINDS, ItemKind
from app.resume.document import document_text
from app.resume.options import TONE_OPTIONS
from app.schemas.items import validate_item_data
from app.services.profile_service import ItemView

_LEADING_NUMBER = re.compile(r"^\s*(?:\d+[.)]|[-•*])\s*")
_TONES = {t["key"] for t in TONE_OPTIONS}


def facts_from_views(views: list[ItemView], *, profile_summary: str | None = None) -> str:
    """The student's facts as plain lines, each marked verified or self-declared: everything the model may say."""
    lines: list[str] = []
    for view in views:
        d, tag = view.data, "verified" if view.item.verified else "self-declared"
        kind = view.item.kind
        if kind == "experience":
            lines.append(f"({tag}) Experience: {d.get('title')} at {d.get('company')} {d.get('start_date', '')}–{d.get('end_date', 'present')}. " + " ".join(d.get("bullets") or []))
        elif kind == "education":
            lines.append(f"({tag}) Education: {d.get('degree')} {d.get('field_of_study', '')}, {d.get('institution')}. {d.get('grade', '')}")
        elif kind == "project":
            lines.append(f"({tag}) Project: {d.get('name')}. {d.get('description', '')} Technologies: {', '.join(d.get('technologies') or [])}. " + " ".join(d.get("bullets") or []))
        elif kind == "skill":
            lines.append(f"({tag}) Skill: {d.get('name')}")
        elif kind == "achievement":
            lines.append(f"({tag}) Achievement: {d.get('title')}. {d.get('description', '')}")
        elif kind == "certificate":
            lines.append(f"({tag}) Certificate: {view.derived.get('course_title', 'Course')}" + (f", grade {d['grade']}" if d.get("grade") else ""))
        elif kind == "skill_score":
            lines.append(f"({tag}) Assessment: {view.derived.get('course_title', 'Course')}, best score {d.get('best_percent'):g}%")
        elif kind == "course":
            lines.append(f"({tag}) Completed course: {view.derived.get('course_title', 'Course')}")
    if profile_summary:
        lines.append(f"(self-declared) About: {profile_summary}")
    return "\n".join(line.strip() for line in lines)


class AiService:
    def __init__(self, settings: Settings, gateway: GatewayClient) -> None:
        self.settings = settings
        self.gateway = gateway

    async def _complete(self, *, organization_id: int | None, user_id: int, prompt_key: str, variables: dict[str, str], content: str, key: str | None = None) -> str:
        try:
            done = await self.gateway.complete(
                organization_id=organization_id or self.settings.PLATFORM_ORGANIZATION_ID, user_id=user_id, prompt_key=prompt_key, variables=variables,
                messages=[{"role": "user", "content": content}], idempotency_key=key,
            )
        except GatewayQuotaExceeded as exc:
            raise AiQuotaExceededError() from exc
        except GatewayDisabled as exc:
            raise AiDisabledError() from exc
        except GatewayError as exc:
            raise AiUnavailableError() from exc
        if done.status != "ok" or not done.content.strip():
            raise ValidationFailedError("The AI could not help with that text. Try rewording it.", code="AI_CONTENT_BLOCKED")
        return done.content.strip()

    @staticmethod
    def _suggestion(source: str, output: str, *, extra: list[Finding] | None = None, **fields: Any) -> dict[str, Any]:
        findings = [*invented(source, output), *(extra or [])]
        return {**fields, "text": output, "applicable": not findings, "warnings": [f.as_dict() for f in findings], "language_issues": [i.code for i in check_text(output) if i.severity != "tip"]}

    async def summary(self, *, organization_id: int | None, user_id: int, views: list[ItemView], profile_summary: str | None, target_role: str | None, tone: str | None) -> dict[str, Any]:
        facts = facts_from_views(views)
        if not facts:
            raise ValidationFailedError("Add some education, projects, skills or experience to your profile first: there is nothing to summarise yet.", code="NO_FACTS")
        tone = tone if tone in _TONES else "professional"
        text = await self._complete(
            organization_id=organization_id, user_id=user_id, prompt_key="career.summary", variables={"target_role": target_role or "an entry-level role", "tone": tone}, content=f"FACTS:\n{facts}"
        )
        return self._suggestion(facts + "\n" + (target_role or ""), text)

    async def rewrite(self, *, organization_id: int | None, user_id: int, bullets: list[str], context: str | None) -> list[dict[str, Any]]:
        numbered = "\n".join(f"{i}. {b}" for i, b in enumerate(bullets, 1))
        raw = await self._complete(
            organization_id=organization_id, user_id=user_id, prompt_key="career.rewrite", variables={"context": context or "a student's resume"}, content=f"BULLETS:\n{numbered}"
        )
        lines = [_LEADING_NUMBER.sub("", line).strip() for line in raw.splitlines() if line.strip()]
        if len(lines) != len(bullets):
            raise AiUnavailableError("The AI's answer was not in the expected shape. Please try again.", code="AI_BAD_OUTPUT")
        results = []
        for original, rewritten in zip(bullets, lines, strict=True):
            results.append(
                {
                    **self._suggestion(original + "\n" + (context or ""), rewritten, original=original),
                    # a deterministic nudge, never a made-up number: the student supplies the metric if they have one
                    "metric_prompt": None if any(c.isdigit() for c in rewritten) else "If you know the scale or result (how many, how much, how fast), add it in your own words.",
                }
            )
        return results

    async def polish(self, *, organization_id: int | None, user_id: int, text: str, tone: str | None) -> dict[str, Any]:
        out = await self._complete(
            organization_id=organization_id, user_id=user_id, prompt_key="career.polish", variables={"tone": tone if tone in _TONES else "professional"}, content=f"TEXT:\n{text}"
        )
        return self._suggestion(text, out, original=text)

    async def read_resume(self, *, organization_id: int | None, user_id: int, text: str) -> tuple[dict[str, str | None], list[dict[str, Any]], int]:
        """An old resume's text -> proposed profile entries (nothing is saved here; the student picks what to keep)."""
        raw = await self._complete(organization_id=organization_id, user_id=user_id, prompt_key="career.import", variables={}, content=f"RESUME:\n{text}")
        return parse_import(text, raw)

    async def tailor_summary(
        self, *, organization_id: int | None, user_id: int, views: list[ItemView], profile_summary: str | None, target_role: str | None, keywords: list[str]
    ) -> dict[str, Any]:
        """A summary that leans on the job's keywords the student's facts already support. A keyword the facts lack is reported
        (and the suggestion refused) rather than written in."""
        facts = facts_from_views(views)
        emphasise = [k for k in keywords if k in facts.lower()]
        text = await self._complete(
            organization_id=organization_id, user_id=user_id, prompt_key="career.summary", variables={"target_role": target_role or "the advertised role", "tone": "professional"},
            content=f"FACTS:\n{facts}\n\nEmphasise these, only where the facts support them: {', '.join(emphasise) or 'none'}",
        )
        source = facts + "\n" + (target_role or "")  # the role the student chose is theirs to name
        return self._suggestion(source, text, extra=unsupported_keywords(source, text, keywords))


_DATE_FIELDS = {"start_date", "end_date", "date"}  # reformatted from the text (Jun 2024 -> 2024-06), so not compared word for word
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _checked_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in data.items():
        if key in _DATE_FIELDS or isinstance(value, bool) or value is None:
            continue
        parts.extend(str(v) for v in value) if isinstance(value, list) else parts.append(str(value))
    return "\n".join(parts)


_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*|\d[\d,.]*")


def _copied_from(source: str, text: str) -> bool:
    """An imported entry must be copied, not written: no number, link or name the file lacks (the general guard), and no
    capitalised word — a company, school, tool — that does not appear in the file, even as a one-word value like a skill."""
    if invented(source, text):
        return False
    words = {t.lower().strip(".-,") for t in _TOKEN.findall(source)}
    for token in _TOKEN.findall(text):
        clean = token.strip(".-,")
        if (clean[:1].isupper() or clean[:1].isdigit()) and clean.lower() not in words and clean.lower() not in source.lower():
            return False
    return True


def parse_import(source: str, raw: str) -> tuple[dict[str, str | None], list[dict[str, Any]], int]:
    """The model's reading of an old resume, kept only where it holds up: every entry must be a valid profile item and must not
    say anything (a number, name, link) the file does not. Returns (profile fields, entries, how many were dropped)."""
    try:
        parsed = json.loads(_FENCE.sub("", raw.strip()))
    except json.JSONDecodeError as exc:
        raise AiUnavailableError("The AI's answer was not in the expected shape. Please try again.", code="AI_BAD_OUTPUT") from exc
    if not isinstance(parsed, dict):
        raise AiUnavailableError("The AI's answer was not in the expected shape. Please try again.", code="AI_BAD_OUTPUT")
    profile: dict[str, str | None] = {}
    for name, limit in (("headline", 160), ("summary", 1_000), ("phone", 30), ("location", 120)):
        value = parsed.get(name)
        profile[name] = value.strip()[:limit] if isinstance(value, str) and value.strip() and not invented(source, value) else None
    items, skipped = [], 0
    for entry in parsed.get("items") or []:
        try:
            kind = ItemKind(entry["kind"])
            if kind not in SELF_KINDS:
                raise ValueError(kind)
            data = validate_item_data(kind, entry.get("data") or {})
        except (KeyError, TypeError, ValueError, ValidationFailedError):
            skipped += 1
            continue
        if not _copied_from(source, _checked_text(data)):
            skipped += 1
            continue
        items.append({"kind": kind.value, "data": data})
    return profile, items, skipped


def gap_report(job_description: str, document: dict[str, Any], views: list[ItemView], profile_summary: str | None) -> dict[str, Any]:
    """Keyword gap analysis: what the job wants, what this resume already says, what the *profile* says but the resume leaves out
    (worth adding), and what appears nowhere (add only if it is true — this service will not add it for you)."""
    resume_text = document_text(document)
    profile_text = facts_from_views(views, profile_summary=profile_summary)
    coverage = kw.coverage(job_description, resume_text)
    profile_words = " ".join(kw.tokens(profile_text))
    present = [k for k in coverage if k.present]
    missing = [k for k in coverage if not k.present]
    in_profile = [k.term for k in missing if f" {' '.join(kw.tokens(k.term))} " in f" {profile_words} "]
    nowhere = [k.term for k in missing if k.term not in in_profile]
    weight = sum(k.weight for k in coverage) or 1
    return {
        "match_percent": round(100 * sum(k.weight for k in present) / weight), "keywords": [{"term": k.term, "weight": k.weight, "present": k.present} for k in coverage],
        "add_from_profile": in_profile, "not_in_profile": nowhere,
        "advice": "Add the terms in `add_from_profile` where they are true. The terms in `not_in_profile` are skills or experience you have not recorded: add them to your profile only if you really have them.",
    }
