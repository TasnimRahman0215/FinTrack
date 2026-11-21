"""FastAPI application entry point.

`uvicorn app.main:app` (local dev and the Docker image) imports `app` from here. This module wires
together settings, logging, CORS, the CSRF guard, error handlers, the /api/v1 routes and, when
RUN_SCHEDULER=true, the background sync scheduler.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import INSECURE_DEFAULT_SECRET, check_runtime_settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import get_engine

log = logging.getLogger("fintrack")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-requested-with"


# Runs once at startup (before `yield`) and once at shutdown (after it).
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    check_runtime_settings(settings)
    get_engine()
    if settings.secret_key == INSECURE_DEFAULT_SECRET:
        log.warning(
            "SECRET_KEY is the insecure default. Run `fintrack gen-keys` and set it in .env."
        )
    if not settings.encryption_key:
        log.warning("ENCRYPTION_KEY is not set; adding SimpleFIN connections will fail.")

    scheduler = None
    if settings.run_scheduler:
        from app.jobs.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    # The interactive docs describe every endpoint; they're handy in development but there's no
    # reason to publish them from a production server.
    docs = not settings.is_production
    app = FastAPI(
        title="FinTrack API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )

    # CORS is only needed when the frontend is served from another origin; the default
    # setup (Vite proxy or nginx) is same-origin and skips it.
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        is_api = request.url.path.startswith("/api/")
        # Browsers can't add custom headers to cross-site form posts, and cross-origin fetches
        # with them need a CORS preflight. Requiring this header on writes blocks CSRF.
        if is_api and request.method not in SAFE_METHODS and CSRF_HEADER not in request.headers:
            response = JSONResponse(
                {"detail": "Missing X-Requested-With header.", "code": "csrf"}, status_code=403
            )
        else:
            response = await call_next(request)
        # API responses hold financial data: never store them in browser or proxy caches
        # (e.g. so the back button on a shared computer can't show them after sign-out).
        if is_api:
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
