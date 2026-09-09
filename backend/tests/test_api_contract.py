import asyncio
from datetime import datetime, timedelta
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

    assert response == {
        "status": main.INTERRUPTED_SYNC_STATUS,
        "last_parsed_at": None,
    }
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


class MaintenanceSession:
    def __init__(self, candidates):
        self.candidates = candidates
        self.commits = 0

    def query(self, _model):
        return self

    def filter(self, *_args):
        return self

    def all(self):
        return self.candidates

    def count(self):
        return len(self.candidates)

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def make_candidate(**overrides):
    current_hash = main.cv_content_hash("old text")
    values = {
        "id": 1,
        "name": "Candidate",
        "cv_url": "https://docs.google.com/document/d/doc-id/edit",
        "cv_text": "old text",
        "cv_source_revision": "revision-1",
        "cv_content_hash": current_hash,
        "parsed_content_hash": current_hash,
        "parsed_with_version": main.CURRENT_CV_PARSER_VERSION,
        "cv_source_check_failures": 0,
        "cv_source_next_check_at": None,
        "stack": "Python",
        "seniority": "Senior",
        "direction": "Backend",
        "embedding": b"existing-vector",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_cv_text_sync_uses_revision_and_hash(monkeypatch):
    unchanged = make_candidate(id=1, cv_url="unchanged", cv_source_revision="r1")
    metadata_only = make_candidate(id=2, cv_url="metadata", cv_source_revision="r1")
    changed = make_candidate(id=3, cv_url="changed", cv_source_revision="r1")
    failed = make_candidate(id=4, cv_url="failed", cv_source_revision="r1")
    skipped = make_candidate(id=5, cv_url="invalid")
    session = MaintenanceSession([unchanged, metadata_only, changed, failed, skipped])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "extract_doc_id", lambda url: None if url == "invalid" else url)

    def metadata_batch(urls):
        values = {
            "unchanged": SimpleNamespace(revision="r1", mime_type="", error=None),
            "metadata": SimpleNamespace(revision="r2", mime_type="", error=None),
            "changed": SimpleNamespace(revision="r2", mime_type="", error=None),
            "failed": SimpleNamespace(
                revision=None,
                mime_type="",
                error=RuntimeError("drive unavailable"),
            ),
        }
        return [values[url] for url in urls]

    def snapshot(url, known_revision, _metadata):
        assert known_revision == "r1"
        if url == "metadata":
            return SimpleNamespace(revision="r2", text="old text")
        if url == "changed":
            return SimpleNamespace(revision="r2", text="new\r\ntext ")
        raise RuntimeError("drive unavailable")

    monkeypatch.setattr(main, "get_doc_metadata_batch", metadata_batch)
    monkeypatch.setattr(main, "get_doc_snapshot", snapshot)

    result = asyncio.run(main.internal_update_cv_texts())

    assert result == {
        "checked": 5,
        "updated": 1,
        "unchanged": 2,
        "skipped": 1,
        "errors": 1,
    }
    assert metadata_only.cv_source_revision == "r2"
    assert metadata_only.embedding == b"existing-vector"
    assert changed.cv_text == "new\ntext"
    assert changed.cv_content_hash == main.cv_content_hash("new\ntext")
    assert changed.parsed_content_hash == main.cv_content_hash("old text")
    assert changed.embedding is None
    assert failed.cv_source_revision == "r1"
    assert failed.cv_text == "old text"
    assert failed.cv_source_check_failures == 1
    assert failed.cv_source_next_check_at is not None


def test_cv_text_sync_commits_revision_progress_in_batches(monkeypatch):
    candidates = [make_candidate(id=index, cv_url=f"doc-{index}") for index in range(101)]
    session = MaintenanceSession(candidates)
    batch_sizes = []
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "extract_doc_id", lambda url: url)

    def metadata_batch(urls):
        batch_sizes.append(len(urls))
        return [
            SimpleNamespace(revision="revision-1", mime_type="", error=None)
            for _ in urls
        ]

    monkeypatch.setattr(main, "get_doc_metadata_batch", metadata_batch)

    result = asyncio.run(main.internal_update_cv_texts())

    assert result["unchanged"] == 101
    assert session.commits == 2
    assert batch_sizes == [100, 1]


def test_cv_text_sync_skips_candidate_during_backoff(monkeypatch):
    candidate = make_candidate(
        cv_source_check_failures=2,
        cv_source_next_check_at=datetime.utcnow() + timedelta(hours=1),
    )
    session = MaintenanceSession([candidate])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        main,
        "get_doc_metadata_batch",
        lambda _urls: (_ for _ in ()).throw(AssertionError("must be skipped")),
    )

    result = asyncio.run(main.internal_update_cv_texts())

    assert result["checked"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == 0


def test_drive_retry_delay_is_longer_for_permanent_errors():
    transient = RuntimeError("connection refused")
    permanent = RuntimeError("not found")
    permanent.resp = SimpleNamespace(status=404)

    assert main.drive_retry_delay(transient, 1) == timedelta(minutes=5)
    assert main.drive_retry_delay(transient, 2) == timedelta(minutes=10)
    assert main.drive_retry_delay(permanent, 1) == timedelta(days=1)
    assert main.drive_retry_delay(permanent, 4) == timedelta(days=7)


def test_incremental_parser_skips_unchanged_and_retries_failures(monkeypatch):
    unchanged = make_candidate(id=1)
    changed = make_candidate(
        id=2,
        cv_text="new text",
        cv_content_hash=main.cv_content_hash("new text"),
    )
    outdated_parser = make_candidate(id=3, parsed_with_version=0)
    failed = make_candidate(
        id=4,
        cv_text="broken text",
        cv_content_hash=main.cv_content_hash("broken text"),
    )
    session = MaintenanceSession([unchanged, changed, outdated_parser, failed])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    def parse(text):
        if text == "broken text":
            raise ValueError("cannot parse")
        return {"stack": "Go" if text == "new text" else "Python", "seniority": "Senior", "direction": "Backend"}

    monkeypatch.setattr(main, "extract_all_from_text", parse)
    result = main.internal_parse_cv_stacks()

    assert result["checked"] == 4
    assert result["updated"] == 2
    assert result["unchanged"] == 1
    assert result["errors"] == 1
    assert changed.parsed_content_hash == changed.cv_content_hash
    assert changed.embedding is None
    assert outdated_parser.parsed_with_version == main.CURRENT_CV_PARSER_VERSION
    assert outdated_parser.embedding == b"existing-vector"
    assert failed.parsed_content_hash != failed.cv_content_hash


def test_second_incremental_parse_does_no_work_and_force_reparses(monkeypatch):
    candidate = make_candidate(
        cv_text="new text",
        cv_content_hash=main.cv_content_hash("new text"),
    )
    session = MaintenanceSession([candidate])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    calls = []

    def parse(text):
        calls.append(text)
        return {"stack": "Python", "seniority": "Senior", "direction": "Backend"}

    monkeypatch.setattr(main, "extract_all_from_text", parse)

    first = main.internal_parse_cv_stacks()
    second = main.internal_parse_cv_stacks()
    forced = main.internal_parse_cv_stacks(force=True)

    assert first["updated"] == 1
    assert second["updated"] == 0
    assert second["unchanged"] == 1
    assert forced["updated"] == 1
    assert calls == ["new text", "new text"]


def test_embeddings_only_use_successfully_parsed_current_content(monkeypatch):
    ready = make_candidate(id=1, embedding=None)
    dirty = make_candidate(
        id=2,
        embedding=None,
        cv_content_hash=main.cv_content_hash("new text"),
    )
    session = MaintenanceSession([ready, dirty])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    calls = []
    monkeypatch.setattr(main, "embed", lambda text: calls.append(text) or [1.0])
    monkeypatch.setattr(
        main.np,
        "array",
        lambda *_args, **_kwargs: SimpleNamespace(tobytes=lambda: b"vector"),
    )

    result = main.internal_build_embeddings()

    assert result["checked"] == 1
    assert result["updated"] == 1
    assert calls == ["Python\nold text"]
    assert dirty.embedding is None


def test_parser_commits_in_batches(monkeypatch):
    candidates = [
        make_candidate(
            id=index,
            cv_text=f"text-{index}",
            cv_content_hash=main.cv_content_hash(f"text-{index}"),
        )
        for index in range(101)
    ]
    session = MaintenanceSession(candidates)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        main,
        "extract_all_from_text",
        lambda _text: {"stack": "Python", "seniority": "Senior", "direction": "Backend"},
    )

    result = main.internal_parse_cv_stacks()

    assert result["updated"] == 101
    assert session.commits == 2


def test_parse_endpoint_forwards_force_and_releases_lock(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.chdir(tmp_path)

    def parse(days_limit=None, force=False):
        captured.update(days_limit=days_limit, force=force)
        return {"updated": 0}

    monkeypatch.setattr(main, "internal_parse_cv_stacks", parse)

    assert main.parse_cv_stacks(days_limit=7, force=True) == {"updated": 0}
    assert captured == {"days_limit": 7, "force": True}
    saved_timestamp = (tmp_path / main.LAST_CV_PARSING_FILE).read_text()
    parsed_timestamp = datetime.fromisoformat(saved_timestamp.replace("Z", "+00:00"))
    assert parsed_timestamp.utcoffset().total_seconds() == 0
    assert not main._sync_lock.locked()


def test_sync_status_returns_last_parsing_timestamp(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    completed_status = "Синхронизация полностью завершена"
    Path("sync_status.txt").write_text(completed_status, encoding="utf-8")
    Path(main.LAST_CV_PARSING_FILE).write_text(
        "2026-09-09T09:30:00Z", encoding="utf-8"
    )

    assert main.get_sync_status() == {
        "status": completed_status,
        "last_parsed_at": "2026-09-09T09:30:00Z",
    }


def test_nightly_job_checks_all_cv_revisions(monkeypatch):
    captured = []
    session = MaintenanceSession([])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "sync_candidates_from_cloud", lambda _session: {})

    async def process(days_limit=None):
        captured.append(days_limit)

    monkeypatch.setattr(main, "process_cvs_in_background", process)

    main.nightly_maintenance_job()

    assert captured == [None]
    assert not main._sync_lock.locked()
