from fastapi import APIRouter

from app.api.routes import analytics, categories, health, imports, telegram, transactions

api_router = APIRouter()
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(categories.router, tags=["categories"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(imports.router, tags=["imports"])
api_router.include_router(telegram.router, tags=["telegram"])
api_router.include_router(transactions.router, tags=["transactions"])

