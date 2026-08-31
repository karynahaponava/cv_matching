import asyncio
import logging
from typing import Any
from uuid import uuid4

import requests
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any | None = None
    trace_id: str


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Некорректный запрос"},
    404: {"model": ErrorResponse, "description": "Ресурс не найден"},
    409: {"model": ErrorResponse, "description": "Конфликт состояния"},
    422: {"model": ErrorResponse, "description": "Ошибка валидации"},
    429: {"model": ErrorResponse, "description": "Превышен лимит запросов"},
    500: {"model": ErrorResponse, "description": "Внутренняя ошибка"},
    502: {"model": ErrorResponse, "description": "Ошибка внешнего сервиса"},
    504: {"model": ErrorResponse, "description": "Таймаут внешнего сервиса"},
}


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid4()))


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        details=details,
        trace_id=_trace_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        headers={"X-Trace-ID": payload.trace_id},
    )


def external_service_error(
    exc: Exception,
    *,
    code: str,
    message: str,
) -> ApiError:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, requests.Timeout)):
        return ApiError(504, code, message)

    response_status = getattr(getattr(exc, "resp", None), "status", None)
    if response_status == 429:
        return ApiError(
            429,
            "RATE_LIMIT_EXCEEDED",
            "Внешний сервис временно ограничил количество запросов",
        )

    return ApiError(502, code, message)


def install_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        request.state.trace_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Trace-ID"] = request.state.trace_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        if exc.status_code >= 500:
            logger.error(
                "API error %s [trace_id=%s]",
                exc.code,
                _trace_id(request),
                exc_info=exc.__cause__ or exc,
            )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return _error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Запрос не прошёл валидацию",
            details=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        codes = {
            400: "INVALID_REQUEST",
            404: "RESOURCE_NOT_FOUND",
            409: "CONFLICT",
            429: "RATE_LIMIT_EXCEEDED",
            502: "EXTERNAL_SERVICE_ERROR",
            504: "EXTERNAL_SERVICE_TIMEOUT",
        }
        message = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
        return _error_response(
            request,
            status_code=exc.status_code,
            code=codes.get(exc.status_code, "HTTP_ERROR"),
            message=message,
            details=None if isinstance(exc.detail, str) else exc.detail,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        trace_id = _trace_id(request)
        logger.exception("Unhandled API error [trace_id=%s]", trace_id, exc_info=exc)
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="Внутренняя ошибка сервера",
        )
