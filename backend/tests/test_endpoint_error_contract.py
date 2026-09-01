import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient


EXPECTED_ERROR_STATUSES = {400, 404, 409, 422, 429, 500, 502, 504}
EXPECTED_ENDPOINTS = {
    ("GET", "/"),
    ("POST", "/sync-excel"),
    ("POST", "/update-cv-texts"),
    ("POST", "/parse-cv-stacks"),
    ("POST", "/build-embeddings"),
    ("POST", "/fuzzy-match"),
    ("POST", "/semantic-match"),
    ("GET", "/search"),
    ("GET", "/sync-status"),
    ("POST", "/analyze-cv"),
    ("POST", "/sync-vacancies"),
    ("GET", "/vacancies"),
    ("GET", "/vacancy-departments"),
    ("GET", "/departments"),
    ("POST", "/parse-tg"),
    ("POST", "/save-tg-vacancy"),
    ("GET", "/saved-tg-vacancies"),
}


class FakeColumn:
    def __eq__(self, other):
        return self

    def __ne__(self, other):
        return self

    def __ge__(self, other):
        return self

    def __lt__(self, other):
        return self

    def is_(self, other):
        return self

    def is_not(self, other):
        return self

    def in_(self, other):
        return self

    def desc(self):
        return self


class FakeModel:
    id = FakeColumn()
    name = FakeColumn()
    cv_url = FakeColumn()
    cv_text = FakeColumn()
    stack = FakeColumn()
    direction = FakeColumn()
    embedding = FakeColumn()
    created_at = FakeColumn()
    department = FakeColumn()
    candidate_id = FakeColumn()

    def __init__(self, **values):
        self.__dict__.update(values)


class FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def with_entities(self, *args):
        return self

    def order_by(self, *args):
        return self

    def distinct(self):
        return self

    def offset(self, value):
        return self

    def limit(self, value):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def scalar(self):
        return 0

    def count(self):
        return 0


class FakeSession:
    def query(self, *args):
        return FakeQuery()

    def add(self, value):
        return None

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def _module(name: str, **attributes) -> ModuleType:
    module = ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    return module


def _install_main_import_stubs() -> None:
    numpy = _module(
        "numpy",
        float32=float,
        array=lambda value, dtype=None: value,
        frombuffer=lambda value, dtype=None: SimpleNamespace(tolist=lambda: []),
    )
    numpy.linalg = SimpleNamespace(norm=lambda value: 0)

    sqlalchemy = _module(
        "sqlalchemy",
        func=SimpleNamespace(
            length=lambda value: FakeColumn(),
            count=lambda value: FakeColumn(),
        ),
        or_=lambda *args: FakeColumn(),
    )
    sqlalchemy.__path__ = []

    scheduler_module = _module("apscheduler.schedulers.background")

    class FakeScheduler:
        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def shutdown(self):
            return None

    scheduler_module.BackgroundScheduler = FakeScheduler
    _module("apscheduler").__path__ = []
    _module("apscheduler.schedulers").__path__ = []

    class GoogleHttpError(Exception):
        pass

    _module("googleapiclient").__path__ = []
    _module("googleapiclient.errors", HttpError=GoogleHttpError)

    base = SimpleNamespace(metadata=SimpleNamespace(create_all=lambda bind: None))
    _module("database").__path__ = []
    _module(
        "database.db",
        Base=base,
        SessionLocal=lambda: FakeSession(),
        engine=object(),
    )
    _module(
        "database.models",
        Candidate=FakeModel,
        Submission=FakeModel,
        Vacancy=FakeModel,
        TelegramVacancy=FakeModel,
        TelegramChannelState=FakeModel,
    )

    _module("services").__path__ = []
    _module("services.google_docs", get_doc_text=lambda url: "")
    _module(
        "services.google_sheets",
        sync_candidates_from_cloud=lambda session: {"added_candidates": 0},
        sync_vacancies_from_cloud=lambda session, backfill=False: {
            "added": 0,
            "updated": 0,
            "skipped": 0,
        },
    )
    _module("services.cv_parser", extract_all_from_text=lambda text: {})
    _module(
        "services.fuzzy_search",
        fuzzy_search_candidates=lambda **kwargs: [],
        get_candidate_badge=lambda *args: (None, None),
    )
    _module("services.matcher", calculate_match_score=lambda query, text: 0)
    _module(
        "services.embeddings",
        embed=lambda text: [],
        cosine_similarity=lambda first, second: 0,
        model=SimpleNamespace(encode=lambda values: []),
    )
    _module("services.tg_scraper", fetch_tg_channel_posts=lambda url, limit: [])


@pytest.fixture(scope="session")
def api_module():
    _install_main_import_stubs()
    sys.modules.pop("main", None)
    return importlib.import_module("main")


@pytest.fixture()
def client(api_module, monkeypatch):
    monkeypatch.setattr(api_module, "update_status", lambda text: None)
    monkeypatch.setattr(api_module.os.path, "exists", lambda path: False)
    test_client = TestClient(api_module.app, raise_server_exceptions=False)
    yield test_client
    test_client.close()


def assert_error_contract(response, expected_status: int) -> dict:
    assert response.status_code == expected_status
    payload = response.json()
    assert set(payload) == {"code", "message", "details", "trace_id"}
    assert isinstance(payload["code"], str) and payload["code"]
    assert isinstance(payload["message"], str) and payload["message"]
    assert payload["trace_id"]
    assert response.headers["X-Trace-ID"] == payload["trace_id"]
    return payload


def test_every_endpoint_documents_the_common_error_responses(api_module):
    routes = {
        (method, route.path): route
        for route in api_module.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert set(routes) == EXPECTED_ENDPOINTS
    for route in routes.values():
        assert EXPECTED_ERROR_STATUSES <= set(route.responses)


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "expected_status"),
    [
        ("post", "/fuzzy-match", {"json": {"keywords": []}}, 422),
        ("post", "/semantic-match", {"json": {"query": ""}}, 422),
        ("get", "/search", {}, 422),
        ("post", "/analyze-cv", {"json": {}}, 422),
        ("post", "/parse-tg", {"json": {}}, 422),
        ("post", "/save-tg-vacancy", {"json": {}}, 422),
        ("get", "/vacancies?page=0", {}, 422),
        ("get", "/saved-tg-vacancies?page_size=101", {}, 422),
        ("post", "/sync-vacancies?backfill=invalid", {}, 422),
    ],
)
def test_endpoint_validation_errors_use_common_contract(
    client,
    method,
    path,
    kwargs,
    expected_status,
):
    response = getattr(client, method)(path, **kwargs)
    payload = assert_error_contract(response, expected_status)
    assert payload["code"] == "VALIDATION_ERROR"


def test_all_endpoints_have_expected_success_or_domain_response(client):
    cases = [
        ("get", "/", {}, 200),
        ("post", "/sync-excel", {}, 200),
        ("post", "/update-cv-texts", {}, 200),
        ("post", "/parse-cv-stacks", {}, 200),
        ("post", "/build-embeddings", {}, 200),
        ("post", "/fuzzy-match", {"json": {"keywords": ["python"]}}, 200),
        ("post", "/semantic-match", {"json": {"query": "python"}}, 200),
        ("get", "/search?query=python", {}, 200),
        ("get", "/sync-status", {}, 200),
        ("post", "/analyze-cv", {"json": {"query": "python", "cv_url": "x"}}, 404),
        ("post", "/sync-vacancies", {}, 200),
        ("get", "/vacancies", {}, 200),
        ("get", "/vacancy-departments", {}, 200),
        ("get", "/departments", {}, 200),
        ("post", "/parse-tg", {"json": {"url": "https://t.me/test"}}, 200),
        (
            "post",
            "/save-tg-vacancy",
            {"json": {"channel": "test", "text": "vacancy"}},
            200,
        ),
        ("get", "/saved-tg-vacancies", {}, 200),
    ]

    for method, path, kwargs, expected_status in cases:
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == expected_status, (path, response.text)
        assert response.headers["X-Trace-ID"]
        if expected_status >= 400:
            assert_error_contract(response, expected_status)


def test_search_rejects_blank_query_with_400(client):
    response = client.get("/search", params={"query": "   "})
    payload = assert_error_contract(response, 400)
    assert payload["code"] == "INVALID_SEARCH_QUERY"


def test_sync_rejects_parallel_run_with_409(client, api_module):
    api_module._sync_lock.acquire()
    try:
        response = client.post("/sync-excel")
    finally:
        api_module._sync_lock.release()

    payload = assert_error_contract(response, 409)
    assert payload["code"] == "SYNC_IN_PROGRESS"


@pytest.mark.parametrize(
    ("error_factory", "expected_status"),
    [
        (lambda module: module.GoogleHttpError("external failure"), 502),
        (lambda module: module.requests.Timeout("external timeout"), 504),
        (lambda module: RuntimeError("internal failure"), 500),
    ],
)
def test_sync_failures_use_common_contract(
    client,
    api_module,
    monkeypatch,
    error_factory,
    expected_status,
):
    error = error_factory(api_module)
    monkeypatch.setattr(
        api_module,
        "sync_candidates_from_cloud",
        lambda session: (_ for _ in ()).throw(error),
    )

    response = client.post("/sync-excel")
    payload = assert_error_contract(response, expected_status)
    assert payload["code"] == "SYNC_FAILED"


def test_external_rate_limit_from_sync_uses_429(client, api_module, monkeypatch):
    error = api_module.GoogleHttpError("rate limited")
    error.resp = SimpleNamespace(status=429)
    monkeypatch.setattr(
        api_module,
        "sync_candidates_from_cloud",
        lambda session: (_ for _ in ()).throw(error),
    )

    response = client.post("/sync-excel")
    payload = assert_error_contract(response, 429)
    assert payload["code"] == "RATE_LIMIT_EXCEEDED"
