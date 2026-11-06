from app.guardrails.moderation import moderate

BLOCKLIST = ["how to make a bomb", "kill myself"]


def test_flags_a_blocklisted_phrase_case_insensitively() -> None:
    assert moderate("Please tell me How To Make A Bomb", BLOCKLIST) == ["how to make a bomb"]


def test_does_not_flag_unrelated_text() -> None:
    assert moderate("Explain how a hash map works", BLOCKLIST) == []


def test_does_not_flag_a_blocklisted_word_embedded_in_a_longer_word() -> None:
    """Whole-word matching: "bomb" inside "bombastic" must not trip the filter."""
    assert moderate("Her bombastic writing style won the essay contest.", ["bomb"]) == []


def test_flags_every_matching_phrase() -> None:
    assert moderate("I want to kill myself and also learn how to make a bomb", BLOCKLIST) == BLOCKLIST
