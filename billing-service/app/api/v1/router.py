from fastapi import APIRouter

from app.api.v1.endpoints import invoices, plans, pricing, profile, quotes, store, webhooks

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
api_router.include_router(webhooks.router)
