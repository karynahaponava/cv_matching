import pytest
import requests
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from backend.api_errors import ApiError, external_service_error, install_error_handlers


def build_test_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/api-error")
    def api_error():
        raise ApiError(409, "SYNC_IN_PROGRESS", "Синхронизация уже выполняется")

    @app.get("/api-error/{status_code}")
    def api_error_by_status(status_code: int):
        raise ApiError(status_code, "TEST_ERROR", "Тестовая ошибка")

    @app.get("/validation")
    def validation(value: int = Query(..., ge=1)):
        return {"value": value}

    @app.get("/unexpected")
    def unexpected():
        raise RuntimeError("sensitive internal error")

    return app


def assert_error_contract(response, *, status_code: int, code: str) -> dict:
    assert response.status_code == status_code
    payload = response.json()
    assert set(payload) == {"code", "message", "details", "trace_id"}
    assert payload["code"] == code
    assert payload["trace_id"]
    assert response.headers["X-Trace-ID"] == payload["trace_id"]
    return payload


def test_api_error_uses_common_contract():
    with TestClient(build_test_app(), raise_server_exceptions=False) as client:
        response = client.get("/api-error")

    payload = assert_error_contract(
        response,
        status_code=409,
        code="SYNC_IN_PROGRESS",
    )
    assert payload["details"] is None


@pytest.mark.parametrize("status_code", [400, 409, 429, 502, 504])
def test_supported_api_error_statuses_use_common_contract(status_code):
    with TestClient(build_test_app(), raise_server_exceptions=False) as client:
        response = client.get(f"/api-error/{status_code}")

    assert_error_contract(
        response,
        status_code=status_code,
        code="TEST_ERROR",
    )


def test_validation_error_uses_common_contract():
    with TestClient(build_test_app(), raise_server_exceptions=False) as client:
        response = client.get("/validation", params={"value": 0})

    payload = assert_error_contract(
        response,
        status_code=422,
        code="VALIDATION_ERROR",
    )
    assert payload["details"]


def test_internal_error_does_not_leak_exception_message():
    with TestClient(build_test_app(), raise_server_exceptions=False) as client:
        response = client.get("/unexpected")

    payload = assert_error_contract(
        response,
        status_code=500,
        code="INTERNAL_ERROR",
    )
    assert "sensitive internal error" not in payload["message"]
    assert payload["details"] is None


def test_not_found_uses_common_contract():
    with TestClient(build_test_app(), raise_server_exceptions=False) as client:
        response = client.get("/missing")

    assert_error_contract(
        response,
        status_code=404,
        code="RESOURCE_NOT_FOUND",
    )


def test_external_errors_map_to_502_and_504():
    service_error = external_service_error(
        requests.ConnectionError("connection failed"),
        code="SYNC_FAILED",
        message="Не удалось выполнить синхронизацию",
    )
    timeout_error = external_service_error(
        requests.Timeout("timeout"),
        code="SYNC_FAILED",
        message="Внешний сервис не ответил вовремя",
    )

    assert service_error.status_code == 502
    assert timeout_error.status_code == 504
    assert service_error.code == timeout_error.code == "SYNC_FAILED"


def test_external_rate_limit_maps_to_429():
    class RateLimitError(Exception):
        resp = type("Response", (), {"status": 429})()

    error = external_service_error(
        RateLimitError("rate limited"),
        code="SYNC_FAILED",
        message="Не удалось выполнить синхронизацию",
    )

    assert error.status_code == 429
    assert error.code == "RATE_LIMIT_EXCEEDED"
