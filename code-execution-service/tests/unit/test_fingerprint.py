from app.domain.enums import LanguageKind
from app.utils.fingerprint import fingerprint, similarity_percent, tokenize

ORIGINAL = """
def total(xs):
    result = 0
    for x in xs:
        result += x * 2
    return result

print(total([1, 2, 3]))
"""
# Same program, everything cosmetic changed: names, literals, comments, layout.
DISGUISED = """
# my own solution
def compute(values):
    acc = 0
    for v in values:
        acc += v * 9   # nine
    return acc
print(compute([7, 8, 9]))
"""
UNRELATED = """
import sys
n = int(sys.stdin.readline())
print(sum(range(n)) if n > 0 else -1)
for line in sys.stdin:
    print(line.strip()[::-1])
"""


def _fp(source: str, kind: LanguageKind = LanguageKind.PROGRAM) -> set[int]:
    return fingerprint(source, kind, min_tokens=10, max_hashes=500)


def test_renaming_and_reformatting_does_not_change_the_fingerprint() -> None:
    assert _fp(ORIGINAL) == _fp(DISGUISED)


def test_a_different_program_shares_nothing() -> None:
    assert not _fp(ORIGINAL) & _fp(UNRELATED)


def test_similarity_is_containment_of_the_smaller_program() -> None:
    assert similarity_percent(8, 10, 40) == 80
    assert similarity_percent(0, 10, 40) == 0
    assert similarity_percent(5, 0, 40) == 0
    assert similarity_percent(12, 10, 10) == 100  # never above 100


def test_a_program_too_short_to_judge_has_no_fingerprint() -> None:
    assert _fp("print(1)") == set()


def test_tokens_hide_identifiers_strings_and_numbers_but_keep_keywords() -> None:
    assert tokenize('if x > 10: print("hi")') == ["if", "ID", ">", "NUM", ":", "ID", "(", "STR", ")"]


def test_a_decrement_is_code_in_a_program_but_a_comment_in_sql() -> None:
    assert tokenize("i--; next()") == ["ID", "-", "-", ";", "ID", "(", ")"]
    assert tokenize("SELECT 1 -- pick one\nFROM t", LanguageKind.SQL) == ["select", "NUM", "from", "ID"]


def test_comments_are_dropped() -> None:
    assert tokenize("a = 1 // one\n/* block\nspanning */ b = 2 # hash") == ["ID", "=", "NUM", "ID", "=", "NUM"]


def test_the_fingerprint_is_capped_and_stable() -> None:
    long_source = "\n".join(f"if a{i} > {i}: b{i} = a{i} + {i}" for i in range(400))
    capped = fingerprint(long_source, min_tokens=10, max_hashes=50)
    assert len(capped) <= 50
    assert capped == fingerprint(long_source, min_tokens=10, max_hashes=50)  # the same sample every time
