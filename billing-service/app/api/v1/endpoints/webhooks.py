"""The payment gateway's callback. Not bearer-authenticated: the body's HMAC-SHA256 signature is the credential (``X-Razorpay-Signature``, or ``X-Signature`` for the generic contract)."""

from fastapi import APIRouter, Request

from app.api.deps import DbSession, PaymentGatewayDep, SettingsDep
from app.api.responses import errors
from app.schemas.billing import WebhookResponse
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/payment", response_model=WebhookResponse, summary="Payment provider callback", responses=errors(401, 422),
             description="Verified by signature, de-duplicated by `event_id`, applied to the invoice under its lock. Answers 200 for a duplicate or an unknown order so the provider stops retrying.")
async def payment_webhook(request: Request, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> WebhookResponse:
    headers = {k.lower(): v for k, v in request.headers.items()}
    result = await PaymentService(db, settings, gateway).handle_webhook(await request.body(), headers)
    return WebhookResponse(status="success", result=result)
