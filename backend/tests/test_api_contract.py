from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from api_errors import ApiError
from services import fuzzy_search


@pytest.fixture(autouse=True)
def reset_process_local_state():
    main.rate_limiter.reset()
    if main._sync_lock.locked():
        main._sync_lock.release()
    yield
    if main._sync_lock.locked():
        main._sync_lock.release()


def test_paginated_response_empty_and_non_empty():
    assert main.paginated_response([], 3, 50, 0) == {
        "items": [],
        "pagination": {
            "page": 3,
            "page_size": 50,
            "total": 0,
            "total_pages": 0,
        },
    }
    response = main.paginated_response([{"id": 1}], 1, 50, 51)
    assert response["pagination"]["total_pages"] == 2


def test_request_defaults_and_collection_limits():
    semantic = main.SemanticMatchRequest(query="python")
    assert (semantic.page, semantic.page_size) == (1, 50)

    with pytest.raises(ValidationError):
        main.SemanticMatchRequest(query="python", page_size=101)
    with pytest.raises(ValidationError):
        main.FuzzyMatchRequest(keywords=["python"] * 31)
    with pytest.raises(ValidationError):
        main.FuzzyMatchRequest(keywords=["x" * 65])
    with pytest.raises(ValidationError):
        main.FuzzyMatchRequest(keywords=["python"], departments=["d"] * 11)
    with pytest.raises(ValidationError):
        main.SemanticMatchRequest(query="python", departments=["d"] * 11)


def test_query_length_validation_returns_422():
    client = TestClient(main.app)
    long_query = "x" * 2001
    assert client.post("/semantic-match", json={"query": long_query}).status_code == 422
    assert client.get("/search", params={"query": long_query}).status_code == 422
    assert client.post(
        "/analyze-cv", json={"query": long_query, "cv_url": "https://example.test"}
    ).status_code == 422


def test_fuzzy_forwards_departments_and_pagination(monkeypatch):
    captured = {}

    def fake_search(**kwargs):
        captured["kwargs"] = kwargs
        return [{"id": 7}], 101

    monkeypatch.setattr(main, "fuzzy_search_candidates", fake_search)
    request = main.FuzzyMatchRequest(
        keywords=["python"], departments=["Backend"], page=2, page_size=50
    )
    response = main.fuzzy_match(request)

    assert captured["kwargs"]["departments"] == ["Backend"]
    assert captured["kwargs"]["page"] == 2
    assert captured["kwargs"]["page_size"] == 50
    assert response["items"] == [{"id": 7}]
    assert response["pagination"] == {
        "page": 2,
        "page_size": 50,
        "total": 101,
        "total_pages": 3,
    }


def test_fuzzy_sql_receives_department_filter(monkeypatch):
    calls = []

    class Result:
        def scalar(self):
            return 0

        def mappings(self):
            return self

        def all(self):
            return []

    class Session:
        def execute(self, statement, params):
            calls.append((str(statement), params.copy()))
            return Result()

        def close(self):
            pass

    monkeypatch.setattr(fuzzy_search, "SessionLocal", Session)
    assert fuzzy_search.fuzzy_search_candidates(
        ["python"], departments=["Backend"], page=2, page_size=25
    ) == ([], 0)
    assert len(calls) == 2
    assert calls[0][1]["departments"] == ["Backend"]
    assert "c.direction = ANY" in calls[0][0]
    assert calls[1][1]["offset"] == 25


class FakeSearchSession:
    def __init__(self, candidates):
        self.candidates = candidates

    def query(self, _model):
        return self

    def filter(self, *_args):
        return self

    def all(self):
        return self.candidates

    def close(self):
        pass


def test_classic_search_first_last_and_out_of_range_pages(monkeypatch):
    candidates = [
        SimpleNamespace(id=i, name=f"candidate-{i}", cv_url=str(i), stack=str(100 - i), cv_text="")
        for i in range(1, 6)
    ]
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSearchSession(candidates))
    monkeypatch.setattr(main, "calculate_match_score", lambda _query, text: int(text.strip()))

    first = main.search("python", page=1, page_size=2)
    last = main.search("python", page=3, page_size=2)
    beyond = main.search("python", page=4, page_size=2)

    assert [item["id"] for item in first["items"]] == [1, 2]
    assert [item["id"] for item in last["items"]] == [5]
    assert beyond["items"] == []
    assert beyond["pagination"] == {
        "page": 4,
        "page_size": 2,
        "total": 5,
        "total_pages": 3,
    }


def test_rate_limits_are_independent_and_recover_after_window():
    now = [0.0]
    limiter = main.SlidingWindowRateLimiter(clock=lambda: now[0])

    for _ in range(30):
        limiter.check("fuzzy", "127.0.0.1", 30)
    for _ in range(10):
        limiter.check("semantic", "127.0.0.1", 10)

    with pytest.raises(ApiError) as fuzzy_error:
        limiter.check("fuzzy", "127.0.0.1", 30)
    with pytest.raises(ApiError) as semantic_error:
        limiter.check("semantic", "127.0.0.1", 10)
    assert fuzzy_error.value.status_code == 429
    assert semantic_error.value.status_code == 429
    assert fuzzy_error.value.headers["Retry-After"] == "60"

    limiter.check("fuzzy", "127.0.0.2", 30)

    now[0] = 61.0
    limiter.check("fuzzy", "127.0.0.1", 30)
    limiter.check("semantic", "127.0.0.1", 10)


def test_search_endpoints_return_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSearchSession([]))
    monkeypatch.setattr(main, "embed", lambda _query: [0.0])
    monkeypatch.setattr(main, "fuzzy_search_candidates", lambda **_kwargs: ([], 0))
    client = TestClient(main.app)

    for _ in range(10):
        assert client.post("/semantic-match", json={"query": "python"}).status_code == 200
    semantic_limited = client.post("/semantic-match", json={"query": "python"})
    assert semantic_limited.status_code == 429
    assert semantic_limited.headers["Retry-After"] == "60"

    for _ in range(30):
        assert client.post("/fuzzy-match", json={"keywords": ["python"]}).status_code == 200
    fuzzy_limited = client.post("/fuzzy-match", json={"keywords": ["python"]})
    assert fuzzy_limited.status_code == 429
    assert fuzzy_limited.headers["Retry-After"] == "60"


def test_maintenance_conflict_and_release_after_exception(monkeypatch):
    main._sync_lock.acquire()
    with pytest.raises(ApiError) as conflict:
        main.acquire_sync_lock()
    assert conflict.value.status_code == 409
    main._sync_lock.release()

    def fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "internal_parse_cv_stacks", fail)
    with pytest.raises(RuntimeError):
        main.parse_cv_stacks(None)
    assert not main._sync_lock.locked()


@pytest.mark.parametrize(
    "operation",
    [
        lambda: main.sync_excel(BackgroundTasks()),
        lambda: main.sync_vacancies(False),
    ],
)
def test_maintenance_lock_released_when_session_creation_fails(monkeypatch, operation):
    monkeypatch.setattr(
        main,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    with pytest.raises(ApiError):
        operation()
    assert not main._sync_lock.locked()


def test_stale_running_sync_status_is_marked_interrupted(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status_file = Path("sync_status.txt")
    status_file.write_text(
        "Шаг 2: Скачивание текстов резюме для ВСЕЙ базы...",
        encoding="utf-8",
    )

    response = main.get_sync_status()

    assert response == {"status": main.INTERRUPTED_SYNC_STATUS}
    assert status_file.read_text(encoding="utf-8") == main.INTERRUPTED_SYNC_STATUS


def test_active_sync_status_is_not_recovered(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status_file = Path("sync_status.txt")
    running_status = "Шаг 3: Анализ стека..."
    status_file.write_text(running_status, encoding="utf-8")
    main._sync_lock.acquire()

    assert main.recover_stale_sync_status() is None
    assert status_file.read_text(encoding="utf-8") == running_status


@pytest.mark.parametrize(
    "terminal_status",
    [
        "🎉 Синхронизация полностью завершена!",
        "❌ Процесс прерван из-за ошибки",
        "Синхронизация еще не запускалась",
    ],
)
def test_terminal_sync_status_is_preserved(monkeypatch, tmp_path, terminal_status):
    monkeypatch.chdir(tmp_path)
    status_file = Path("sync_status.txt")
    status_file.write_text(terminal_status, encoding="utf-8")

    assert main.recover_stale_sync_status() == terminal_status
    assert status_file.read_text(encoding="utf-8") == terminal_status
