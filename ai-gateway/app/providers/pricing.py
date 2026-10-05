"""Cost in cents per 1,000 tokens, used only to attribute spend to an org (``OrgUsage.cost_cents_used``,
``AiCallLog.cost_cents``) for the budget guardrail and future billing — this service never charges a card.

These figures are illustrative placeholders, not fetched from a live pricing page (this environment has no network
access) — check them against the provider's current pricing before relying on the cost figures for anything billed.
An unlisted model falls back to ``_DEFAULT``, so a call is still priced, just not precisely.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceRate:
    prompt_cents_per_1k: float
    completion_cents_per_1k: float


_DEFAULT = PriceRate(prompt_cents_per_1k=0.3, completion_cents_per_1k=1.5)

_CHAT_PRICES: dict[str, PriceRate] = {
    "claude-haiku-4-5-20251001": PriceRate(prompt_cents_per_1k=0.1, completion_cents_per_1k=0.5),
    "claude-sonnet-5": PriceRate(prompt_cents_per_1k=0.3, completion_cents_per_1k=1.5),
    "claude-opus-5": PriceRate(prompt_cents_per_1k=1.5, completion_cents_per_1k=7.5),
}
_EMBEDDING_PRICES: dict[str, PriceRate] = {
    "voyage-3": PriceRate(prompt_cents_per_1k=0.002, completion_cents_per_1k=0.0),
}


def chat_cost_cents(model: str, *, prompt_tokens: int, completion_tokens: int) -> int:
    rate = _CHAT_PRICES.get(model, _DEFAULT)
    cents = prompt_tokens / 1000 * rate.prompt_cents_per_1k + completion_tokens / 1000 * rate.completion_cents_per_1k
    return round(cents)


def embedding_cost_cents(model: str, *, tokens: int) -> int:
    rate = _EMBEDDING_PRICES.get(model, PriceRate(prompt_cents_per_1k=0.01, completion_cents_per_1k=0.0))
    return round(tokens / 1000 * rate.prompt_cents_per_1k)
