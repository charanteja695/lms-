from app.providers.pricing import chat_cost_cents, embedding_cost_cents


def test_chat_cost_scales_with_tokens() -> None:
    small = chat_cost_cents("claude-sonnet-5-5", prompt_tokens=1_000, completion_tokens=1_000)
    large = chat_cost_cents("claude-sonnet-5-5", prompt_tokens=2_000, completion_tokens=2_000)
    assert large == small * 2
    assert small > 0


def test_completion_tokens_cost_more_than_prompt_tokens() -> None:
    prompt_only = chat_cost_cents("claude-sonnet-5-5", prompt_tokens=1_000, completion_tokens=0)
    completion_only = chat_cost_cents("claude-sonnet-5-5", prompt_tokens=0, completion_tokens=1_000)
    assert completion_only > prompt_only


def test_an_unknown_model_still_gets_priced() -> None:
    assert chat_cost_cents("some-future-model", prompt_tokens=1_000, completion_tokens=1_000) > 0


def test_zero_tokens_cost_nothing() -> None:
    assert chat_cost_cents("claude-sonnet-5-5", prompt_tokens=0, completion_tokens=0) == 0
    assert embedding_cost_cents("voyage-3", tokens=0) == 0


def test_embedding_cost_scales_with_tokens() -> None:
    # Embeddings cost a tiny fraction of a cent per call in reality, so this needs a large batch to clear the
    # integer-cent rounding and actually show the doubling (see the module docstring on why cents, not fractions).
    small = embedding_cost_cents("voyage-3", tokens=1_000_000)
    large = embedding_cost_cents("voyage-3", tokens=2_000_000)
    assert small > 0
    assert large == small * 2
