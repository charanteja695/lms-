"""Plagiarism fingerprints: winnowing over a normalised token stream (Schleimer, Wilkerson & Aiken).

Renaming variables, changing whitespace, comments or literal values does not change the fingerprint,
because identifiers become ``ID``, strings ``STR`` and numbers ``NUM`` and comments are dropped. Only keywords
and the program's structure remain, so two solutions with the same shape match however they are dressed up.

Language-agnostic on purpose: one tokenizer for every language keeps this service free of per-language
parsers, at the cost of being a similarity signal for a human reviewer, never proof of copying.
"""

import hashlib
import re

from app.domain.enums import LanguageKind

K_GRAM = 5  # tokens per hashed gram
WINDOW = 4  # grams per winnowing window

# Words that are reserved in mainstream languages and unlikely to be someone's variable name. Ambiguous words
# (``set``, ``type``, ``values``, ``index``, ``string``...) are deliberately absent: treating a variable as a
# keyword would make a renamed copy look different.
_PROGRAM_KEYWORDS = frozenset(
    """
    if else elif elsif unless for foreach while do until loop break continue return yield def fn func function fun
    class struct enum interface trait impl namespace package import include using require public private protected
    static final const let var val mut int long short float double char bool boolean void auto unsigned signed new
    delete try catch except finally raise throw throws switch case default in is not and or lambda async await goto
    with pass none null nil true false self this super extends implements override virtual abstract template
    typename operator sizeof
    """.split()
)
# SQL is judged on structure too, but there the reserved words are the structure.
_SQL_KEYWORDS = frozenset(
    """
    select from where group by order having join inner outer left right full cross on union all distinct into
    insert update delete values set create table drop alter limit offset as and or not in is null like between
    exists case when then else end asc desc with recursive over partition count sum avg min max
    """.split()
)

_TOKEN = re.compile(
    r"""
      (?P<block>/\*.*?\*/)
    | (?P<line>//[^\n]*|\#[^\n]*)
    | (?P<sqlline>--[^\n]*)
    | (?P<string>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`[^`]*`)
    | (?P<number>\d+(?:\.\d+)?)
    | (?P<word>[A-Za-z_]\w*)
    | (?P<symbol>[^\s\w])
    """,
    re.VERBOSE | re.DOTALL,
)


def tokenize(source: str, kind: LanguageKind = LanguageKind.PROGRAM) -> list[str]:
    keywords = _SQL_KEYWORDS if kind == LanguageKind.SQL else _PROGRAM_KEYWORDS
    tokens: list[str] = []
    for match in _TOKEN.finditer(source):
        group = match.lastgroup
        text = match.group()
        if group in {"block", "line"}:
            continue
        if group == "sqlline":
            if kind == LanguageKind.PROGRAM:  # `i--` is an operator in most languages, a comment only in SQL
                tokens.extend(["-", "-"])
                tokens.extend(tokenize(text[2:], kind))  # the rest of the line is code, not a comment
            continue
        if group == "string":
            tokens.append("STR")
        elif group == "number":
            tokens.append("NUM")
        elif group == "word":
            tokens.append(text.lower() if text.lower() in keywords else "ID")
        else:
            tokens.append(text)
    return tokens


def _hash(gram: tuple[str, ...]) -> int:
    digest = hashlib.blake2b("\x00".join(gram).encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") >> 1  # 63 bits: fits a signed BIGINT


def fingerprint(source: str, kind: LanguageKind = LanguageKind.PROGRAM, *, min_tokens: int, max_hashes: int) -> set[int]:
    """The winnowed hash set of ``source``; empty when the program is too short to say anything about."""
    tokens = tokenize(source, kind)
    if len(tokens) < max(min_tokens, K_GRAM):
        return set()
    hashes = [_hash(tuple(tokens[i : i + K_GRAM])) for i in range(len(tokens) - K_GRAM + 1)]
    if len(hashes) <= WINDOW:
        selected = {min(hashes)}
    else:
        selected = set()
        for start in range(len(hashes) - WINDOW + 1):
            selected.add(min(hashes[start : start + WINDOW]))
    if len(selected) > max_hashes:  # keep the smallest: a stable sample, the same on every run
        selected = set(sorted(selected)[:max_hashes])
    return selected


def similarity_percent(shared: int, size_a: int, size_b: int) -> int:
    """How much of the smaller program's fingerprint appears in the other (containment, 0-100)."""
    smaller = min(size_a, size_b)
    return 0 if smaller == 0 else min(100, round(100 * shared / smaller))
