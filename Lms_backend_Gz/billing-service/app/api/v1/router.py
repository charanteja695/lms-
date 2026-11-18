from fastapi import APIRouter

from app.api.v1.endpoints import (
    institution_payments,
    institutional_requests,
    invoices,
    plans,
    pricing,
    profile,
    quotes,
    store,
    student_subscriptions,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(profile.router)
api_router.include_router(profile.admin)
api_router.include_router(pricing.router)
api_router.include_router(pricing.admin)
api_router.include_router(quotes.router)
api_router.include_router(quotes.admin)
api_router.include_router(invoices.router)
api_router.include_router(invoices.admin)
api_router.include_router(plans.router)
api_router.include_router(store.router)
api_router.include_router(student_subscriptions.admin_plans_router)
api_router.include_router(student_subscriptions.admin_settings_router)
api_router.include_router(student_subscriptions.admin_tx_router)
api_router.include_router(student_subscriptions.admin_reports_router)
api_router.include_router(student_subscriptions.student_router)
api_router.include_router(institution_payments.student_requests_router)
api_router.include_router(institution_payments.institution_payments_router)
api_router.include_router(institution_payments.admin_requests_router)
api_router.include_router(institutional_requests.institution_router)
api_router.include_router(institutional_requests.admin_router)
api_router.include_router(webhooks.router)
