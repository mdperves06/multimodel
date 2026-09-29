from fastapi import APIRouter

from app.api import accounts, auth, providers

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(providers.router)
api_router.include_router(accounts.router)
