from fastapi import APIRouter

from app.api import accounts, audit, auth, gallery, jobs, providers, usage

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(providers.router)
api_router.include_router(accounts.router)
api_router.include_router(jobs.router)
api_router.include_router(gallery.router)
api_router.include_router(usage.router)
api_router.include_router(audit.router)
