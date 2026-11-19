"""Application exceptions, rendered as `{"detail": str, "code": str}` JSON responses.

Services raise these instead of FastAPI's HTTPException, so business code doesn't depend on the
web layer. `detail` is shown to users by the frontend (src/api/client.js); `code` is a stable
machine-readable value the frontend can branch on.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class. Subclasses only change the default HTTP status and code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class TooManyRequests(AppError):
    status_code = 429
    code = "rate_limited"


class ServiceBusy(AppError):
    status_code = 503
    code = "busy"


class ConfigError(AppError):
    status_code = 500
    code = "config_error"


class ProviderError(AppError):
    """A data provider (e.g. SimpleFIN) failed or returned something unexpected."""

    status_code = 502
    code = "provider_error"


class ProviderAuthError(ProviderError):
    """The provider rejected stored credentials; the user must reconnect."""

    code = "provider_auth"


def register_exception_handlers(app: FastAPI) -> None:
    """Called by app/main.py. Unexpected exceptions still become a plain 500 with no details."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status_code)
