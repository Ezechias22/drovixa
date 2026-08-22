from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def error_response(
    *, code: str, message: str, status_code: int, request: Request, details: Any | None = None
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        error["request_id"] = request_id
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": error},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request=request,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
            for item in exc.errors()
        ]
        return error_response(
            code="VALIDATION_ERROR",
            message="The request data is invalid.",
            status_code=422,
            request=request,
            details=details,
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, _: IntegrityError) -> JSONResponse:
        return error_response(
            code="CONFLICT",
            message="The operation conflicts with existing data.",
            status_code=409,
            request=request,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = (
            "The requested resource was not found." if exc.status_code == 404 else str(exc.detail)
        )
        return error_response(
            code=code, message=message, status_code=exc.status_code, request=request
        )
