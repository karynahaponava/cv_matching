import os
import re
import io
import json
import random
import threading
import time
from dataclasses import dataclass

import docx
import google_auth_httplib2
import httplib2
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_DOC_ID_PATTERNS = (
    re.compile(r"/document/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"),
)


@dataclass(frozen=True)
class DocumentSnapshot:
    revision: str | None
    text: str | None


@dataclass(frozen=True)
class DocumentMetadata:
    revision: str | None = None
    mime_type: str = ""
    error: Exception | None = None


@dataclass
class _GoogleServices:
    credentials: object
    drive: object
    docs: object
    drive_http: object


_thread_local = threading.local()
BATCH_SIZE = 100
BATCH_ATTEMPTS = 3
HTTP_TIMEOUT_SECONDS = 15
BATCH_DEADLINE_SECONDS = 50
RETRYABLE_403_REASONS = {
    "rateLimitExceeded",
    "userRateLimitExceeded",
}


def extract_doc_id(url: str) -> str | None:
    if not url:
        return None
    for pattern in _DOC_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _get_credentials():
    creds_path = os.getenv("GOOGLE_CREDS_PATH")
    if not creds_path:
        raise ValueError("GOOGLE_CREDS_PATH is not set")
    return service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )


def _get_services() -> _GoogleServices:
    """Reuse API clients within a worker without sharing httplib2 across threads."""
    services = getattr(_thread_local, "google_services", None)
    if services is None:
        credentials = _get_credentials()
        drive_http = google_auth_httplib2.AuthorizedHttp(
            credentials,
            http=httplib2.Http(timeout=HTTP_TIMEOUT_SECONDS),
        )
        docs_http = google_auth_httplib2.AuthorizedHttp(
            credentials,
            http=httplib2.Http(timeout=HTTP_TIMEOUT_SECONDS),
        )
        services = _GoogleServices(
            credentials=credentials,
            drive=build(
                "drive", "v3", http=drive_http, cache_discovery=False
            ),
            docs=build(
                "docs", "v1", http=docs_http, cache_discovery=False
            ),
            drive_http=drive_http,
        )
        _thread_local.google_services = services
    return services


def _read_paragraph_element(element: dict) -> str:
    text_run = element.get("textRun")
    if not text_run:
        return ""
    return text_run.get("content", "")


def _read_structural_elements(elements: list) -> str:
    text = ""
    for value in elements:
        if "paragraph" in value:
            for elem in value["paragraph"].get("elements", []):
                text += _read_paragraph_element(elem)
        elif "table" in value:
            for row in value["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    text += _read_structural_elements(cell.get("content", []))
        elif "tableOfContents" in value:
            text += _read_structural_elements(
                value["tableOfContents"].get("content", [])
            )
    return text


def _fetch_via_docs_api(service, doc_id: str) -> str:
    document = service.documents().get(documentId=doc_id).execute(num_retries=2)
    content = document.get("body", {}).get("content", [])
    return _read_structural_elements(content).strip()


def _fetch_via_drive_export(service, doc_id: str, mime_type: str) -> str:
    if mime_type == "application/vnd.google-apps.document":
        raw = service.files().export(
            fileId=doc_id, mimeType="text/plain"
        ).execute(num_retries=2)
        if isinstance(raw, bytes):
            return raw.decode("utf-8").strip()
        return str(raw).strip()

    elif mime_type == "application/pdf":
        request = service.files().get_media(fileId=doc_id)
        file_content = request.execute(num_retries=2)
        reader = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()

    elif (
        mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        request = service.files().get_media(fileId=doc_id)
        file_content = request.execute(num_retries=2)
        doc = docx.Document(io.BytesIO(file_content))

        full_text = [p.text for p in doc.paragraphs]

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        full_text.append(cell.text.strip())

        return "\n".join(full_text)

    return ""


def _revision_token(metadata: dict) -> str | None:
    version = metadata.get("version")
    modified_time = metadata.get("modifiedTime")
    if version is None and not modified_time:
        return None
    return f"version={version or ''};modifiedTime={modified_time or ''}"


def drive_error_reasons(error: Exception) -> set[str]:
    if not isinstance(error, HttpError):
        return set()
    try:
        content = (
            error.content.decode("utf-8")
            if isinstance(error.content, bytes)
            else error.content
        )
        payload = json.loads(content)
    except (AttributeError, TypeError, ValueError):
        return set()

    details = payload.get("error", {}).get("errors", [])
    return {
        str(detail.get("reason"))
        for detail in details
        if isinstance(detail, dict) and detail.get("reason")
    }


def is_retryable_drive_error(error: Exception) -> bool:
    if isinstance(error, HttpError):
        status = error.resp.status
        return (
            status == 408
            or status == 429
            or status >= 500
            or (
                status == 403
                and bool(drive_error_reasons(error) & RETRYABLE_403_REASONS)
            )
        )
    return True


def is_permanent_drive_error(error: Exception) -> bool:
    if not isinstance(error, HttpError):
        return False
    if is_retryable_drive_error(error):
        return False
    return error.resp.status in (403, 404)


def get_doc_metadata_batch(doc_urls: list[str]) -> list[DocumentMetadata]:
    """Fetch Drive metadata in batches of up to 100 requests per HTTP call."""
    if len(doc_urls) > BATCH_SIZE:
        raise ValueError(f"Размер batch не должен превышать {BATCH_SIZE}")

    services = _get_services()
    started_at = time.monotonic()
    results: list[DocumentMetadata | None] = [None] * len(doc_urls)
    pending = {
        index: doc_id
        for index, url in enumerate(doc_urls)
        if (doc_id := extract_doc_id(url))
    }
    for index, url in enumerate(doc_urls):
        if not extract_doc_id(url):
            results[index] = DocumentMetadata(
                error=ValueError("Не удалось извлечь ID документа из ссылки")
            )

    for attempt in range(BATCH_ATTEMPTS):
        if not pending or time.monotonic() - started_at >= BATCH_DEADLINE_SECONDS:
            break

        attempt_results: dict[int, DocumentMetadata] = {}

        def callback(request_id, response, exception):
            index = int(request_id)
            if exception is not None:
                attempt_results[index] = DocumentMetadata(error=exception)
                return
            attempt_results[index] = DocumentMetadata(
                revision=_revision_token(response),
                mime_type=response.get("mimeType", ""),
            )

        batch = services.drive.new_batch_http_request(callback=callback)
        for index, doc_id in pending.items():
            batch.add(
                services.drive.files().get(
                    fileId=doc_id,
                    fields="mimeType,version,modifiedTime",
                    supportsAllDrives=True,
                ),
                request_id=str(index),
            )

        outer_error = None
        try:
            batch.execute(http=services.drive_http)
        except Exception as exc:
            outer_error = exc

        retry_pending = {}
        for index, doc_id in pending.items():
            result = attempt_results.get(index)
            if result is None:
                result = DocumentMetadata(
                    error=outer_error or RuntimeError("Drive batch не вернул ответ")
                )

            if (
                result.error is not None
                and is_retryable_drive_error(result.error)
                and attempt + 1 < BATCH_ATTEMPTS
                and time.monotonic() - started_at < BATCH_DEADLINE_SECONDS
            ):
                retry_pending[index] = doc_id
            else:
                results[index] = result

        pending = retry_pending
        if pending:
            remaining = BATCH_DEADLINE_SECONDS - (time.monotonic() - started_at)
            if remaining > 0:
                time.sleep(min(0.5 * (2**attempt) + random.random(), remaining))

    for index in pending:
        if results[index] is None:
            results[index] = DocumentMetadata(
                error=RuntimeError("Drive metadata недоступны после повторных попыток")
            )

    return [result for result in results if result is not None]


def get_doc_snapshot(
    doc_url: str,
    known_revision: str | None = None,
    metadata: DocumentMetadata | None = None,
) -> DocumentSnapshot:
    """Return document metadata and content only when its revision is unknown/new."""
    doc_id = extract_doc_id(doc_url)
    if not doc_id:
        raise ValueError("Не удалось извлечь ID документа из ссылки")

    services = _get_services()
    if metadata is None:
        metadata = get_doc_metadata_batch([doc_url])[0]

    if metadata.error is not None:
        # Some shared Google Docs can still be read through the Docs API even when
        # Drive metadata is unavailable. In that case compare content hashes.
        if not is_permanent_drive_error(metadata.error):
            raise metadata.error
        try:
            text = _fetch_via_docs_api(services.docs, doc_id)
        except Exception:
            raise metadata.error
        if not text:
            raise metadata.error
        return DocumentSnapshot(revision=None, text=text)

    revision = metadata.revision
    if revision and known_revision == revision:
        return DocumentSnapshot(revision=revision, text=None)

    try:
        text = _fetch_via_drive_export(
            services.drive, doc_id, metadata.mime_type
        )
        if text:
            return DocumentSnapshot(revision=revision, text=text)
    except Exception as e:
        print(f"⚠️ Ошибка Drive API для {doc_id}: {e}")

    try:
        text = _fetch_via_docs_api(services.docs, doc_id)
        if text:
            return DocumentSnapshot(revision=revision, text=text)
    except Exception:
        pass

    raise ValueError("Документ пуст, закрыт или имеет неподдерживаемый формат")


def get_doc_text(doc_url: str) -> str:
    """Backward-compatible text fetch used by CV analysis endpoints."""
    try:
        return get_doc_snapshot(doc_url).text or ""
    except Exception:
        return ""
