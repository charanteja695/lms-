"""The payment gateway (docs/PRODUCT.md §5.10, D13). Two providers speak through this one client:

**Razorpay** (``PAYMENT_PROVIDER=razorpay``, the default; configured when ``RAZORPAY_KEY_ID`` and ``RAZORPAY_KEY_SECRET`` are set):
  POST {RAZORPAY_API_URL}/orders  (HTTP basic: key id, key secret)  {amount, currency, receipt, notes}
      -> 200 {"id": "order_...", "amount": n, "currency": "INR", "status": "created"}
  The browser pays in Razorpay's checkout window and gets back ``razorpay_order_id``, ``razorpay_payment_id`` and
  ``razorpay_signature`` = HMAC-SHA256(order_id + "|" + payment_id, key secret), which billing verifies before trusting it.
  Razorpay also calls ``POST /api/v1/webhooks/payment`` signed with ``PAYMENT_WEBHOOK_SECRET`` in ``X-Razorpay-Signature``
  (event id in ``X-Razorpay-Event-Id``): {"event": "payment.captured" | "payment.failed",
  "payload": {"payment": {"entity": {"id", "order_id", "amount", ...}}}}.

**Generic** (``PAYMENT_PROVIDER=generic``; configured when ``PAYMENT_GATEWAY_URL`` is set), a provider-neutral contract:
  POST /orders {amount, currency, receipt}  ->  201 {"order": {"id", "amount", "currency", "status"}}
  webhook signed in ``X-Signature``: {"event_id", "type", "order_id", "payment_id", "amount"}.

Exercised against mocked HTTP transports only; no test talks to a real provider. Manual payments (an admin recording a
bank transfer or cheque) never go through this file and always work.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.gateways.errors import Rejected, Unavailable


class PaymentGatewayNotConfigured(Exception):
    """No provider keys/URL: the deployment takes manual payments only."""


@dataclass(frozen=True, slots=True)
class GatewayOrder:
    order_id: str
    amount: int
    currency: str


@dataclass(frozen=True, slots=True)
class GatewayEventIn:
    """A provider callback, read into one shape whichever provider sent it."""

    event_id: str
    kind: str  # payment.captured | payment.failed | anything else (ignored)
    order_id: str
    payment_id: str | None
    amount: int | None


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def signature_valid(body: bytes, signature: str | None, secret: str) -> bool:
    return bool(signature) and hmac.compare_digest(sign(body, secret), signature or "")


class PaymentGateway:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    @property
    def is_razorpay(self) -> bool:
        return self.settings.PAYMENT_PROVIDER == "razorpay"

    @property
    def configured(self) -> bool:
        if self.is_razorpay:
            return bool(self.settings.RAZORPAY_KEY_ID and self.settings.RAZORPAY_KEY_SECRET.get_secret_value())
        return bool(self.settings.PAYMENT_GATEWAY_URL)

    @property
    def public_key(self) -> str | None:
        """What the browser's checkout window needs (Razorpay's key id); nothing for the generic contract."""
        return self.settings.RAZORPAY_KEY_ID if self.is_razorpay else None

    async def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str] | None = None) -> GatewayOrder:
        if not self.configured:
            raise PaymentGatewayNotConfigured
        if self.is_razorpay:
            base, path = self.settings.RAZORPAY_API_URL, "/orders"
            auth: httpx.BasicAuth | None = httpx.BasicAuth(self.settings.RAZORPAY_KEY_ID, self.settings.RAZORPAY_KEY_SECRET.get_secret_value())
            headers: dict[str, str] = {}
            body: dict[str, Any] = {"amount": amount, "currency": currency, "receipt": receipt[:40], "notes": notes or {}}
        else:
            base, path, auth = self.settings.PAYMENT_GATEWAY_URL, "/orders", None
            headers = {"Authorization": f"Bearer {self.settings.PAYMENT_GATEWAY_API_KEY.get_secret_value()}"}
            body = {"amount": amount, "currency": currency, "receipt": receipt}
        try:
            async with httpx.AsyncClient(base_url=base.rstrip("/"), timeout=self.settings.PAYMENT_GATEWAY_TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post(path, json=body, headers=headers, auth=auth or httpx.USE_CLIENT_DEFAULT)
        except httpx.HTTPError as exc:
            raise Unavailable(f"payment gateway unreachable: {exc.__class__.__name__}") from exc
        if response.status_code in (408, 429) or response.status_code >= 500:
            raise Unavailable(f"payment gateway answered {response.status_code}")
        if response.status_code >= 400:
            raise Rejected(f"payment gateway answered {response.status_code}", status=response.status_code)
        try:
            data = response.json()
            order = data if self.is_razorpay else data["order"]
            return GatewayOrder(order_id=str(order["id"]), amount=int(order["amount"]), currency=str(order["currency"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise Unavailable("payment gateway answered in an unexpected shape") from exc

    def checkout_signature_valid(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        """Razorpay's proof, returned to the browser after paying, that this payment belongs to this order."""
        if not self.is_razorpay or not self.configured:
            return False
        expected = sign(f"{order_id}|{payment_id}".encode(), self.settings.RAZORPAY_KEY_SECRET.get_secret_value())
        return hmac.compare_digest(expected, signature)

    def read_webhook(self, body: bytes, headers: dict[str, str]) -> GatewayEventIn | None:
        """The callback, verified. ``None`` when the signature is wrong; ``ValueError`` when it is signed but malformed."""
        secret = self.settings.PAYMENT_WEBHOOK_SECRET.get_secret_value()
        if self.is_razorpay:
            if not signature_valid(body, headers.get("x-razorpay-signature"), secret):
                return None
            event = json.loads(body)
            entity = ((event.get("payload") or {}).get("payment") or {}).get("entity") or {}
            event_id = headers.get("x-razorpay-event-id") or f"{event.get('event')}:{entity.get('id')}"
            if not entity.get("order_id"):
                raise ValueError("payment.entity.order_id is required")
            return GatewayEventIn(
                event_id=str(event_id), kind=str(event.get("event", "")), order_id=str(entity["order_id"]),
                payment_id=str(entity["id"]) if entity.get("id") else None, amount=int(entity["amount"]) if entity.get("amount") is not None else None,
            )
        if not signature_valid(body, headers.get("x-signature"), secret):
            return None
        event = json.loads(body)
        return GatewayEventIn(
            event_id=str(event["event_id"]), kind=str(event["type"]), order_id=str(event["order_id"]),
            payment_id=str(event["payment_id"]) if event.get("payment_id") else None, amount=int(event["amount"]) if event.get("amount") is not None else None,
        )
