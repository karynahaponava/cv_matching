import html
import os
import re
import requests
import streamlit as st
from api_client import api_error_message

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_KW_RE = re.compile(r"[a-zA-Zа-яА-Я0-9\.+#][a-zA-Zа-яА-Я0-9+#\.\-_/]*")


def _api_get(
    path: str, params: dict | None = None, timeout_s: int = 20
) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", params=params, timeout=timeout_s)


def _api_post(
    path: str, payload: dict | None = None, timeout_s: int = 2400
) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout_s)


def _get_sync_status() -> tuple[str | None, str | None]:
    """Return the current backend sync status or a user-facing error."""
    try:
        response = _api_get("/sync-status")
        if not response.ok:
            return None, api_error_message(
                response,
                "Не удалось получить статус синхронизации",
            )

        payload = response.json()
        if not isinstance(payload, dict):
            return None, "Сервер вернул некорректный статус синхронизации."

        status = str(payload.get("status", "")).strip()
        if not status:
            return None, "Сервер вернул пустой статус синхронизации."

        return status, None
    except (requests.RequestException, ValueError) as exc:
        return None, f"Не удалось получить статус с сервера: {exc}"


def _classify_sync_status(status: str) -> str:
    """Map the existing text-only backend status to a UI state."""
    normalized = status.lower().replace("ё", "е")

    if "еще не запускалась" in normalized:
        return "idle"
    if "ошибка" in normalized or "прерван" in normalized:
        return "failed"
    if "завершена" in normalized:
        return "completed"
    return "running"


def _render_sync_status(status: str) -> None:
    state = _classify_sync_status(status)

    if state == "idle":
        st.caption(status)
    elif state == "completed":
        st.success(status)
    elif state == "failed":
        st.error(status)
    else:
        st.info(f"**В процессе:** {status}")


def _extract_keywords(query: str) -> list[str]:
    q = (query or "").lower()
    kws = [k for k in _KW_RE.findall(q) if len(k) >= 1]
    return list(dict.fromkeys(kws))[:30]


def _highlight_stack(stack: str, query: str) -> str:
    stack_raw = stack or ""
    stack_l = stack_raw.lower()

    keywords = [kw for kw in _extract_keywords(query) if kw in stack_l]
    if not keywords:
        return html.escape(stack_raw)

    escaped = html.escape(stack_raw)
    for kw in sorted(set(keywords), key=len, reverse=True):
        pattern = re.compile(rf"(?i)(?<!\w)({re.escape(kw)})(?!\w)")
        escaped = pattern.sub(
            r'<mark style="background-color: #d4edda; color: #155724;">\1</mark>',
            escaped,
        )
    return escaped


def _render_search_results(
    results: list[dict],
    query: str,
    target_client: str = "",
    target_broker: str = "",
    *,
    fuzzy: bool = False,
):
    if not results:
        st.info("Ничего не найдено.")
        return

    score_label = "Похожесть ИИ" if fuzzy else "Совпадение"

    for cand in results:
        name = cand.get("name") or ""
        stack = cand.get("stack") or ""
        score = float(cand.get("score") or 0.0)
        cv_url = cand.get("cv_url") or ""

        with st.container(border=True):
            header = st.columns([4, 2])
            header[0].markdown(f"**{name}**")
            header[1].markdown(f"**{score_label}: {score:.2f}%**")

            clamped_score = min(max(score, 0.0), 100.0)
            st.markdown(
                f"""
                <div style="background-color: #e9ecef; border-radius: 4px; height: 8px; width: 100%; margin-bottom: 10px;">
                    <div style="background-color: #28a745; width: {clamped_score}%; height: 100%; border-radius: 4px;"></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if stack:
                st.markdown(_highlight_stack(stack, query), unsafe_allow_html=True)
            else:
                st.caption("Стек отсутствует (резюме приватное или еще не распарсено).")

            color = cand.get("badge_color")
            text = cand.get("badge_text")

            if text:
                if color == "red":
                    st.error(f"🔴 {text}")
                elif color == "green":
                    st.success(f"🟢 {text}")
                elif color == "yellow":
                    st.warning(f"🟡 {text}")
                elif color == "blue":
                    st.info(f"🔵 {text}")

            if cv_url:
                st.caption(f"Постоянная ссылка: {cv_url}")


def _reset_search_results():
    st.session_state.search_results = None
    st.session_state.search_pagination = None
    st.session_state.search_context = None


def _fetch_search_page(context: dict, page: int) -> requests.Response:
    common = {"page": page, "page_size": 50}
    if context["mode"] == "semantic":
        return _api_post(
            "/semantic-match",
            payload={
                **common,
                "query": context["query"],
                "target_client": context["target_client"],
                "target_broker": context["target_broker"],
                "departments": context["departments"],
            },
        )
    if context["mode"] == "fuzzy":
        return _api_post(
            "/fuzzy-match",
            payload={
                **common,
                "keywords": context["keywords"],
                "target_client": context["target_client"],
                "target_broker": context["target_broker"],
                "departments": context["departments"],
            },
        )
    return _api_get(
        "/search",
        params={**common, "query": context["query"]},
    )


if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "search_pagination" not in st.session_state:
    st.session_state.search_pagination = None
if "search_context" not in st.session_state:
    st.session_state.search_context = None
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "is_fuzzy" not in st.session_state:
    st.session_state.is_fuzzy = False


st.set_page_config(page_title="CV Matching UI", layout="wide")

st.markdown(
    """
    <style>
        header[data-testid="stHeader"] {
            position: static !important;
        }

        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important; 
            flex-wrap: nowrap !important;
            gap: 0.75rem !important;
        }

        [data-testid="stColumn"] {
            width: 33.33% !important;
            min-width: 0 !important; 
            flex: 1 1 0 !important;
        }

        [data-testid="stColumn"] > div,
        [data-testid="stColumn"] input,
        [data-baseweb="select"] {
            min-width: 0 !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)


_fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment")


@_fragment(run_every="3s")
def _render_sync_controls():
    current_status, status_error = _get_sync_status()
    sync_is_running = (
        current_status is not None
        and _classify_sync_status(current_status) == "running"
    )

    sync_requested = st.button(
        "Синхронизация",
        use_container_width=True,
        type="primary",
        disabled=sync_is_running,
    )

    if sync_requested:
        with st.spinner("Отправка команды на сервер..."):
            try:
                response = _api_post("/sync-excel")
                if response.ok:
                    data = response.json()
                    if isinstance(data, dict) and data.get("status") == "success":
                        st.success(f"**{data.get('message')}**")
                        return
                    message = data.get("message") if isinstance(data, dict) else None
                    st.error(f"Ошибка бэкенда: {message or 'некорректный ответ'}")
                else:
                    st.error(
                        api_error_message(response, "Не удалось запустить синхронизацию")
                    )
            except (requests.RequestException, ValueError) as exc:
                st.error(f"Ошибка подключения к API: {exc}")
        return

    if status_error:
        st.warning(status_error)
    elif current_status is not None:
        _render_sync_status(current_status)


with st.sidebar:
    st.header("Синхронизация данных")
    _render_sync_controls()

st.title("CV Matching System")

st.subheader("Поиск кандидатов по требованиям")

query = st.text_area(
    "Введите стек или требования для поиска",
    value=st.session_state.get("saved_query", ""),
    placeholder="Например: python fastapi postgresql docker",
    height=100,
    key="search_query_input",
    on_change=_reset_search_results,
)

if "auto_search_query" in st.session_state:
    del st.session_state["auto_search_query"]

col1, col2, col3 = st.columns(3)
with col1:
    target_client = st.text_input(
        "Конечный клиент",
        value="",
        key="target_client_input",
        on_change=_reset_search_results,
    )
with col2:
    target_broker = st.text_input(
        "Брокер / Посредник",
        value="",
        key="target_broker_input",
        on_change=_reset_search_results,
    )
with col3:
    try:
        dep_res = _api_get("/departments", timeout_s=5)
        raw_depts = dep_res.json() if dep_res.ok else []

        cleaned_depts = set()
        for department in raw_depts:
            if department:
                normalized = department.replace("C", "С").replace("c", "с").strip()
                cleaned_depts.add(normalized)

        available_departments = sorted(cleaned_depts)
    except Exception:
        available_departments = []

selected_depts = st.multiselect(
    "Отделы",
    options=available_departments,
    key="selected_depts_input",
    placeholder="Выберите отдел",
    on_change=_reset_search_results,
)

fuzzy_enabled = st.checkbox(
    "Включить нечёткий поиск (поиск опечаток)",
    value=False,
    on_change=_reset_search_results,
)
semantic_enabled = st.checkbox(
    "Включить семантический ИИ-поиск (искать по смыслу)",
    value=True,
    on_change=_reset_search_results,
)

if st.button("Начать поиск", type="primary"):
    q = query.strip()
    if not q:
        st.warning("Пожалуйста, введите требования для поиска.")
        _reset_search_results()
    else:
        with st.spinner("Ищу подходящих кандидатов..."):
            try:
                if semantic_enabled:
                    context = {
                        "mode": "semantic",
                        "query": q,
                        "target_client": target_client.strip(),
                        "target_broker": target_broker.strip(),
                        "departments": list(selected_depts),
                    }
                elif fuzzy_enabled:
                    keywords = _extract_keywords(q)
                    if not keywords:
                        st.warning("Не удалось выделить ключевые слова.")
                        _reset_search_results()
                        st.stop()
                    context = {
                        "mode": "fuzzy",
                        "query": q,
                        "keywords": keywords,
                        "target_client": target_client.strip(),
                        "target_broker": target_broker.strip(),
                        "departments": list(selected_depts),
                    }
                else:
                    context = {
                        "mode": "classic",
                        "query": q,
                        "target_client": target_client.strip(),
                        "target_broker": target_broker.strip(),
                        "departments": list(selected_depts),
                    }

                resp = _fetch_search_page(context, page=1)
                if resp.ok:
                    data = resp.json()
                    st.session_state.search_results = data.get("items", [])
                    st.session_state.search_pagination = data.get("pagination", {})
                    st.session_state.search_context = context
                    st.session_state.last_query = q
                    st.session_state.is_fuzzy = context["mode"] == "fuzzy"
                else:
                    st.error(api_error_message(resp, "Ошибка поиска"))
                    _reset_search_results()
            except Exception as e:
                st.error(f"Не удалось связаться с сервером API: {e}")
                _reset_search_results()

if st.session_state.search_results is not None:
    st.write("---")
    pagination = st.session_state.search_pagination or {}
    total = pagination.get("total", len(st.session_state.search_results))

    st.caption(
        f"Показано: {len(st.session_state.search_results)} из {total} найденных."
    )

    _render_search_results(
        st.session_state.search_results,
        st.session_state.last_query,
        target_client=(st.session_state.search_context or {}).get("target_client", ""),
        target_broker=(st.session_state.search_context or {}).get("target_broker", ""),
        fuzzy=st.session_state.is_fuzzy,
    )

    current_page = pagination.get("page", 1)
    total_pages = pagination.get("total_pages", 0)
    if current_page < total_pages:
        if st.button("Показать еще 50"):
            with st.spinner("Загружаю следующую страницу..."):
                try:
                    resp = _fetch_search_page(
                        st.session_state.search_context,
                        page=current_page + 1,
                    )
                    if resp.ok:
                        data = resp.json()
                        st.session_state.search_results.extend(data.get("items", []))
                        st.session_state.search_pagination = data.get("pagination", {})
                        st.rerun()
                    else:
                        st.error(api_error_message(resp, "Ошибка поиска"))
                except Exception as e:
                    st.error(f"Не удалось связаться с сервером API: {e}")
