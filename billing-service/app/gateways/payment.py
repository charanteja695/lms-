"""The payment gateway, as a contract (docs/PRODUCT.md §5.10, D13). Nothing here has ever talked to a real gateway: it is written to the
shape of a typical order/webhook API and exercised only against a mocked HTTP transport — like Judge0, Anthropic and speech before it.
Manual payments (an admin recording a bank transfer or cheque) never go through this file and always work.

Contract this client speaks to ``PAYMENT_GATEWAY_URL``:
  POST /orders {amount, currency, receipt, notes}  ->  201 {"order": {"id": "...", "amount": n, "currency": "INR", "status": "created"}}
and the gateway calls back ``POST /api/v1/webhooks/payment`` with the raw body signed by HMAC-SHA256 (hex) using the shared
``PAYMENT_WEBHOOK_SECRET`` in an ``X-Signature`` header:
  {"event_id": "...", "type": "payment.captured" | "payment.failed", "order_id": "...", "payment_id": "...", "amount": n}
"""

import hashlib
import hmac
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.gateways.errors import Rejected, Unavailable


class PaymentGatewayNotConfigured(Exception):
    """No ``PAYMENT_GATEWAY_URL``: the deployment takes manual payments only."""


@dataclass(frozen=True, slots=True)
class GatewayOrder:
    order_id: str
    amount: int
    currency: str


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def signature_valid(body: bytes, signature: str | None, secret: str) -> bool:
    return bool(signature) and hmac.compare_digest(sign(body, secret), signature or "")


class PaymentGateway:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.settings.PAYMENT_GATEWAY_URL)

    async def create_order(self, *, amount: int, currency: str, receipt: str) -> GatewayOrder:
        if not self.configured:
            raise PaymentGatewayNotConfigured
        headers = {"Authorization": f"Bearer {self.settings.PAYMENT_GATEWAY_API_KEY.get_secret_value()}"}
        try:
            async with httpx.AsyncClient(base_url=self.settings.PAYMENT_GATEWAY_URL.rstrip("/"), timeout=self.settings.PAYMENT_GATEWAY_TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post("/orders", json={"amount": amount, "currency": currency, "receipt": receipt}, headers=headers)
        except httpx.HTTPError as exc:
            raise Unavailable(f"payment gateway unreachable: {exc.__class__.__name__}") from exc
        if response.status_code in (408, 429) or response.status_code >= 500:
            raise Unavailable(f"payment gateway answered {response.status_code}")
        if response.status_code >= 400:
            raise Rejected(f"payment gateway answered {response.status_code}", status=response.status_code)
        try:
            order = response.json()["order"]
            return GatewayOrder(order_id=str(order["id"]), amount=int(order["amount"]), currency=str(order["currency"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise Unavailable("payment gateway answered in an unexpected shape") from exc
