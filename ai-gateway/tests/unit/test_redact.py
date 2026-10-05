from app.guardrails.redact import redact_messages, redact_text


def test_redacts_an_email() -> None:
    result = redact_text("Contact me at aarav.reddy@example.com please")
    assert "aarav.reddy@example.com" not in result.text
    assert "[REDACTED_EMAIL]" in result.text
    assert result.flags == {"pii:email"}


def test_redacts_a_phone_number() -> None:
    result = redact_text("Call me on 9876543210 today")
    assert "9876543210" not in result.text
    assert result.flags == {"pii:phone"}


def test_redacts_a_pan_number() -> None:
    result = redact_text("My PAN is ABCDE1234F for verification")
    assert "ABCDE1234F" not in result.text
    assert result.flags == {"pii:pan"}


def test_redacts_an_aadhaar_like_number_without_double_counting_as_a_phone() -> None:
    result = redact_text("Aadhaar: 1234 5678 9012")
    assert "1234 5678 9012" not in result.text
    assert result.flags == {"pii:aadhaar"}


def test_text_with_no_pii_is_unchanged() -> None:
    result = redact_text("Explain recursion using a simple example.")
    assert result.text == "Explain recursion using a simple example."
    assert result.flags == set()


def test_redact_messages_redacts_every_message_and_unions_flags() -> None:
    messages = [{"role": "user", "content": "email me at a@b.com"}, {"role": "assistant", "content": "sure, no PII here"}]
    redacted, flags = redact_messages(messages)
    assert redacted[0]["content"] == "email me at [REDACTED_EMAIL]"
    assert redacted[1]["content"] == "sure, no PII here"
    assert redacted[0]["role"] == "user"  # non-content fields pass through
    assert flags == {"pii:email"}
