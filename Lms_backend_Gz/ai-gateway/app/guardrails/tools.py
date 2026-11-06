"""Tool allow-listing (docs/PRODUCT.md §5.5: "Prompt-injection defences: tool allow-list, no write actions
without confirmation").

ai-gateway does not execute tools itself — that happens in the calling service (ai-tutor-service looks up
enrolment/attempt/certificate status; it never runs a write action without the student confirming). What this
service enforces is narrower and structural: a prompt version declares which tool *names* it may offer the model
at all (``PromptVersion.allowed_tools``), and a caller cannot smuggle in a different one for that version.
"""

from app.core.exceptions import ValidationFailedError


def check_tools_allowed(requested: list[dict[str, object]], allowed: list[str]) -> None:
    names = [str(tool.get("name")) for tool in requested]
    disallowed = sorted(set(names) - set(allowed))
    if disallowed:
        raise ValidationFailedError(
            f"This prompt version does not allow the tool(s): {', '.join(disallowed)}.",
            code="TOOL_NOT_ALLOWED",
            details=[{"field": "tools", "code": "TOOL_NOT_ALLOWED", "message": name} for name in disallowed],
        )
