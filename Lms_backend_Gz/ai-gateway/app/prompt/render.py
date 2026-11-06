"""Renders a prompt version's template with caller-supplied variables. Pure and dependency-free so it is trivial to
unit test and cannot itself make an outbound call or touch the database.

Placeholders are ``{{name}}`` (double braces, so a template can still contain single ``{``/``}`` — JSON examples in a
system prompt, code snippets — without being misread as a variable). Every placeholder in the template must have a
supplied value; a supplied variable the template does not reference is simply unused, not an error (a caller may
reuse one variables dict across several prompts).
"""

import re

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class MissingVariables(Exception):
    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names
        super().__init__(f"missing template variables: {', '.join(names)}")


def placeholders_in(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def render(template: str, variables: dict[str, str]) -> str:
    needed = placeholders_in(template)
    missing = tuple(sorted(needed - variables.keys()))
    if missing:
        raise MissingVariables(missing)
    return _PLACEHOLDER.sub(lambda m: variables[m.group(1)], template)
