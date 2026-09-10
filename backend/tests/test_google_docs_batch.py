import importlib.util
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import httplib2
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "services" / "google_docs.py"
SPEC = importlib.util.spec_from_file_location("google_docs_under_test", MODULE_PATH)
google_docs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = google_docs
SPEC.loader.exec_module(google_docs)


def make_http_error(status: int, reason: str):
    response = httplib2.Response({"status": str(status), "reason": reason})
    content = json.dumps(
        {"error": {"errors": [{"reason": reason}], "code": status}}
    ).encode("utf-8")
    return google_docs.HttpError(response, content)


class FakeBatch:
    def __init__(self, drive, callback):
        self.drive = drive
        self.callback = callback
        self.requests = []

    def add(self, request, request_id):
        self.requests.append((request_id, request))

    def execute(self, http=None):
        self.drive.executed_batches.append(
            ([request.doc_id for _, request in self.requests], http)
        )
        attempt = len(self.drive.executed_batches)
        for request_id, request in reversed(self.requests):
            error = self.drive.errors.get((attempt, request.doc_id))
            if error is not None:
                self.callback(request_id, None, error)
            else:
                self.callback(
                    request_id,
                    {
                        "mimeType": "application/pdf",
                        "version": request.doc_id,
                        "modifiedTime": "2026-09-09T10:00:00Z",
                    },
                    None,
                )


class FakeDrive:
    def __init__(self, errors=None):
        self.errors = errors or {}
        self.executed_batches = []

    def new_batch_http_request(self, callback):
        return FakeBatch(self, callback)

    def files(self):
        return self

    def get(self, fileId, **_kwargs):
        return SimpleNamespace(doc_id=fileId)


def install_fake_services(monkeypatch, drive):
    drive_http = object()
    monkeypatch.setattr(
        google_docs,
        "_get_services",
        lambda: SimpleNamespace(drive=drive, drive_http=drive_http, docs=object()),
    )
    return drive_http


def test_metadata_batch_preserves_input_order_and_uses_one_http_call(monkeypatch):
    drive = FakeDrive()
    drive_http = install_fake_services(monkeypatch, drive)
    urls = [
        "https://docs.google.com/document/d/first/edit",
        "https://docs.google.com/document/d/second/edit",
    ]

    results = google_docs.get_doc_metadata_batch(urls)

    assert [result.revision for result in results] == [
        "version=first;modifiedTime=2026-09-09T10:00:00Z",
        "version=second;modifiedTime=2026-09-09T10:00:00Z",
    ]
    assert drive.executed_batches == [(["first", "second"], drive_http)]


def test_metadata_batch_retries_rate_limit_403_but_not_permission_403(monkeypatch):
    rate_limited = make_http_error(403, "rateLimitExceeded")
    forbidden = make_http_error(403, "insufficientFilePermissions")
    drive = FakeDrive(
        errors={(1, "retry-me"): rate_limited, (1, "forbidden"): forbidden}
    )
    install_fake_services(monkeypatch, drive)
    monkeypatch.setattr(google_docs.time, "sleep", lambda _seconds: None)

    results = google_docs.get_doc_metadata_batch(
        [
            "https://docs.google.com/document/d/retry-me/edit",
            "https://docs.google.com/document/d/forbidden/edit",
        ]
    )

    assert results[0].error is None
    assert results[1].error is forbidden
    assert [doc_ids for doc_ids, _ in drive.executed_batches] == [
        ["retry-me", "forbidden"],
        ["retry-me"],
    ]
    assert google_docs.is_retryable_drive_error(rate_limited)
    assert not google_docs.is_permanent_drive_error(rate_limited)
    assert google_docs.is_permanent_drive_error(forbidden)


def test_metadata_batch_rejects_more_than_100_documents():
    with pytest.raises(ValueError):
        google_docs.get_doc_metadata_batch(["url"] * 101)


def test_google_clients_are_reused_per_thread_with_explicit_timeout(monkeypatch):
    created_timeouts = []
    built_apis = []
    monkeypatch.setattr(google_docs, "_thread_local", threading.local())
    monkeypatch.setattr(google_docs, "_get_credentials", lambda: object())
    monkeypatch.setattr(
        google_docs.httplib2,
        "Http",
        lambda timeout: created_timeouts.append(timeout) or SimpleNamespace(),
    )
    monkeypatch.setattr(
        google_docs.google_auth_httplib2,
        "AuthorizedHttp",
        lambda credentials, http: SimpleNamespace(credentials=credentials, http=http),
    )
    monkeypatch.setattr(
        google_docs,
        "build",
        lambda api, _version, **_kwargs: built_apis.append(api)
        or SimpleNamespace(api=api),
    )

    first = google_docs._get_services()
    second = google_docs._get_services()

    assert first is second
    assert built_apis == ["drive", "docs"]
    assert created_timeouts == [
        google_docs.HTTP_TIMEOUT_SECONDS,
        google_docs.HTTP_TIMEOUT_SECONDS,
    ]
