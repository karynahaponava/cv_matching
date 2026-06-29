import html
import os
import re
import requests
import streamlit as st
import time

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_KW_RE = re.compile(r"[a-zA-Zа-яА-Я0-9][a-zA-Zа-яА-Я0-9+#\.\-_/]*")


def _api_get(
    path: str, params: dict | None = None, timeout_s: int = 20
) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", params=params, timeout=timeout_s)


def _api_post(
    path: str, payload: dict | None = None, timeout_s: int = 2400
) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout_s)


def _extract_keywords(query: str) -> list[str]:
    q = (query or "").lower()
    kws = [k for k in _KW_RE.findall(q) if len(k) >= 2]
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


st.set_page_config(page_title="CV Matching UI", layout="wide")

with st.sidebar:
    st.header("Синхронизация данных")
    st.caption(f"Бэкенд: `{API_BASE}`")

    if st.button("Синхронизация", use_container_width=True, type="primary"):
        with st.spinner("Отправка команды на сервер..."):
            try:
                res = _api_post("/sync-excel")
                if res.ok:
                    data = res.json()
                    if data.get("status") == "success":
                        st.success(f"**{data.get('message')}**")

                        status_placeholder = st.empty()

                        while True:
                            status_res = _api_get("/sync-status")
                            if status_res.ok:
                                current_status = status_res.json().get("status", "")
                                status_placeholder.info(
                                    f"**В процессе:** {current_status}"
                                )

                                current_status_lower = current_status.lower()
                                if (
                                    "завершена" in current_status_lower
                                    or "прерван" in current_status_lower
                                    or "ошибка" in current_status_lower
                                ):
                                    if "завершена" in current_status_lower:
                                        status_placeholder.success(
                                            f"✅ {current_status}"
                                        )
                                    else:
                                        status_placeholder.error(f"❌ {current_status}")
                                    break
                            else:
                                status_placeholder.warning(
                                    "Не удалось получить статус с сервера..."
                                )
                                break

                            time.sleep(3)

                    else:
                        st.error(f"Ошибка бэкенда: {data.get('message')}")
                else:
                    st.error(f"Ошибка сервера: {res.status_code}")
            except Exception as e:
                st.error(f"Ошибка подключения к API: {e}")

st.title("CV Matching System")

st.subheader("Поиск кандидатов по требованиям")
query = st.text_area(
    "Введите стек или требования для поиска",
    placeholder="Например: python fastapi postgresql docker",
    height=100,
)

col1, col2, col3 = st.columns(3)
with col1:
    target_client = st.text_input("Конечный клиент", value="")
with col2:
    target_broker = st.text_input("Брокер / Посредник", value="")
with col3:
    try:
        dep_res = _api_get("/departments", timeout_s=5)
        available_departments = dep_res.json() if dep_res.ok else []
    except:
        available_departments = []

    selected_depts = st.multiselect(
        "Отделы (оставьте пустым для поиска по всем):", available_departments
    )

fuzzy_enabled = st.checkbox("Включить нечёткий поиск (поиск опечаток)", value=False)
semantic_enabled = st.checkbox(
    "Включить семантический ИИ-поиск (искать по смыслу)", value=True
)

if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "is_fuzzy" not in st.session_state:
    st.session_state.is_fuzzy = False
if "display_limit" not in st.session_state:
    st.session_state.display_limit = 50

if st.button("Начать поиск", type="primary"):
    q = query.strip()
    if not q:
        st.warning("Пожалуйста, введите требования для поиска.")
        st.session_state.search_results = None
    else:
        st.session_state.display_limit = 50
        with st.spinner("Ищу подходящих кандидатов..."):
            try:
                if semantic_enabled:
                    resp = _api_post(
                        "/semantic-match",
                        payload={
                            "query": q,
                            "target_client": target_client.strip(),
                            "target_broker": target_broker.strip(),
                            "departments": selected_depts,
                        },
                    )
                    if resp.ok:
                        st.session_state.search_results = resp.json()
                        st.session_state.last_query = q
                        st.session_state.is_fuzzy = False
                    else:
                        st.error(f"Ошибка семантического поиска: {resp.status_code}")
                        st.session_state.search_results = None

                elif fuzzy_enabled:
                    keywords = _extract_keywords(q)
                    if not keywords:
                        st.warning("Не удалось выделить ключевые слова.")
                        st.session_state.search_results = None
                    else:
                        resp = _api_post(
                            "/fuzzy-match",
                            payload={
                                "keywords": keywords,
                                "target_client": target_client.strip(),
                                "target_broker": target_broker.strip(),
                                "departments": selected_depts,
                            },
                        )
                        if resp.ok:
                            st.session_state.search_results = resp.json()
                            st.session_state.last_query = q
                            st.session_state.is_fuzzy = True
                        else:
                            st.error(f"Ошибка нечёткого поиска: {resp.status_code}")
                            st.session_state.search_results = None

                else:
                    resp = _api_get("/search", params={"query": q})
                    if resp.ok:
                        st.session_state.search_results = resp.json()
                        st.session_state.last_query = q
                        st.session_state.is_fuzzy = False
                    else:
                        st.error(f"Ошибка классического поиска: {resp.status_code}")
                        st.session_state.search_results = None
            except Exception as e:
                st.error(f"Не удалось связаться с сервером API: {e}")
                st.session_state.search_results = None

if st.session_state.search_results is not None:
    st.write("---")
    limit = st.session_state.display_limit
    top_results = st.session_state.search_results[:limit]

    st.caption(
        f"Показано: {len(top_results)} из {len(st.session_state.search_results)} найденных."
    )

    _render_search_results(
        top_results,
        st.session_state.last_query,
        target_client=target_client.strip(),
        target_broker=target_broker.strip(),
        fuzzy=st.session_state.is_fuzzy,
    )

    if limit < len(st.session_state.search_results):
        if st.button("Показать еще 50"):
            st.session_state.display_limit += 50
            st.rerun() 
