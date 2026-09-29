import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import api_router
from app.config import get_settings
from app.db import get_engine, get_session_factory
from app.errors import register_error_handlers
from app.redis_client import get_redis
from app.security.csrf import origin_check_middleware
from app.security.headers import security_headers_middleware
from app.security.ratelimit import rate_limit_middleware
from app.security.redaction import configure_logging
from app.services.providers import sync_providers
from app.workers.worker import start_embedded_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        with get_session_factory()() as db:
            sync_providers(db)
    except Exception:
        logger.exception("provider sync failed (has the database been migrated?)")
    worker = start_embedded_worker() if get_settings().embedded_worker else None
    yield
    if worker:
        worker[1].set()
        worker[0].join(timeout=5)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    # Later registration = outermost. Order: CORS -> headers -> rate limit -> origin check.
    app.middleware("http")(origin_check_middleware)
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(security_headers_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    register_error_handlers(app)
    app.include_router(api_router)

    @app.get("/api/health")
    def health() -> dict[str, object]:
        checks: dict[str, str] = {}
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"
        try:
            get_redis().ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
        ok = all(v == "ok" for v in checks.values())
        return {"status": "ok" if ok else "degraded", "service": settings.app_name, **checks}

    return app


app = create_app()
