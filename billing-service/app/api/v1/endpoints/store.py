"""The learner store: self-registered learners (``store.buy``) see courses on sale, pay with Razorpay and see their purchases."""

from fastapi import APIRouter

from app.api.deps import DbSession, PaymentGatewayDep, RequireLearner, SettingsDep, WriteRateLimit
from app.api.responses import AUTHENTICATED, errors
from app.models.billing import CoursePurchase, Invoice
from app.schemas.billing import (
    BuyRequest,
    BuyResponse,
    CheckoutOut,
    ConfirmPaymentRequest,
    CoursePurchaseOut,
    CoursePurchasePage,
    CoursePurchaseResponse,
    StoreOfferOut,
    StoreOffersResponse,
)
from app.schemas.types import id_field
from app.services.store_service import StoreService

router = APIRouter(prefix="/store", tags=["Learner store"])

CourseIdPath = id_field("course_id", "1755000000000123")
PurchaseIdPath = id_field("purchase_id", "1755000000000456")


def _purchase(purchase: CoursePurchase, invoice: Invoice) -> CoursePurchaseOut:
    out = CoursePurchaseOut.model_validate(purchase)
    return out.model_copy(update={"invoice_number": invoice.number})


@router.get("/offers", response_model=StoreOffersResponse, summary="Courses on sale, with the price to pay (incl. GST)", responses=errors(*AUTHENTICATED))
async def offers(auth: RequireLearner, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> StoreOffersResponse:
    rows = await StoreService(db, settings, gateway).offers()
    return StoreOffersResponse(
        message="", payments_available=gateway.configured,
        offers=[StoreOfferOut(course_id=o.course_id, name=o.name, price=o.price, gst=o.gst, total=o.total, valid_days=o.valid_days) for o in rows],
    )


@router.get("/purchases", response_model=CoursePurchasePage, summary="My purchases", responses=errors(*AUTHENTICATED))
async def my_purchases(auth: RequireLearner, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> CoursePurchasePage:
    return CoursePurchasePage(message="", purchases=[_purchase(p, i) for p, i in await StoreService(db, settings, gateway).mine(auth)])


@router.post(
    "/courses/{course_id}/buy", response_model=BuyResponse, status_code=201, summary="Buy a course: returns the checkout to open",
    description="Invoices the learner at once and opens a Razorpay order for the total. Buying a course you already have extends your access. "
    "A purchase still waiting for payment is reused (with a fresh order).",
    responses=errors(*AUTHENTICATED, 404, 409, 503), dependencies=[WriteRateLimit],
)
async def buy(course_id: CourseIdPath, body: BuyRequest, auth: RequireLearner, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> BuyResponse:  # type: ignore[valid-type]
    service = StoreService(db, settings, gateway)
    purchase, checkout = await service.buy(auth, course_id, name=body.name, email=body.email)
    _, invoice = await service.get_own(auth, purchase.public_id)
    return BuyResponse(
        message="Complete the payment to start the course.", purchase=_purchase(purchase, invoice),
        checkout=CheckoutOut(provider=checkout.provider, key_id=checkout.key_id, order_id=checkout.order_id, amount=checkout.amount, currency=checkout.currency, seller_name=checkout.seller_name),
    )


@router.post(
    "/purchases/{purchase_id}/confirm", response_model=CoursePurchaseResponse, summary="Confirm the payment after the checkout closes",
    description="Verifies Razorpay's signature for this order and payment, then marks the invoice paid; the course opens within moments.",
    responses=errors(*AUTHENTICATED, 400, 404), dependencies=[WriteRateLimit],
)
async def confirm(purchase_id: PurchaseIdPath, body: ConfirmPaymentRequest, auth: RequireLearner, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> CoursePurchaseResponse:  # type: ignore[valid-type]
    purchase, invoice = await StoreService(db, settings, gateway).confirm(
        auth, purchase_id, order_id=body.razorpay_order_id, payment_id=body.razorpay_payment_id, signature=body.razorpay_signature
    )
    message = "Payment received: your course is open." if purchase.status == "paid" else "Payment is being confirmed."
    return CoursePurchaseResponse(message=message, purchase=_purchase(purchase, invoice))
