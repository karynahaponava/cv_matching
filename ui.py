import html
import os
import re
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_KW_RE = re.compile(r"[a-zA-Zа-яА-Я0-9][a-zA-Zа-яА-Я0-9+#\.\-_/]*")


def _api_get(
    path: str, params: dict | None = None, timeout_s: int = 20
) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", params=params, timeout=timeout_s)


def _api_post(
    path: str, payload: dict | None = None, timeout_s: int = 1200
) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout_s)


def _extract_keywords(query: str) -> list[str]:
    q = (query or "").lower()
    kws = [k for k in _KW_RE.findall(q) if len(k) >= 2]
    return list(dict.fromkeys(kws))


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

            st.progress(min(max(score / 100.0, 0.0), 1.0))

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
        with st.spinner(
            "Скачиваем Excel, парсим доступные CV и обновляем ИИ-векторы..."
        ):
            try:
                res = _api_post("/sync-excel")
                if res.ok:
                    data = res.json()
                    if data.get("status") == "success":
                        stats = data.get("stats", {})
                        st.success(
                            f"**База успешно обновлена!**\n\n"
                            f"Новых строк в таблице: {stats.get('updated_submissions', 0)}\n\n"
                            f"Скачано текстов открытых CV: {stats.get('downloaded_cv_texts', 0)}\n\n"
                            f"Распарсено чистых стеков: {stats.get('successfully_parsed_stacks', 0)}"
                        )
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

col1, col2 = st.columns(2)
with col1:
    target_client = st.text_input(
        "Конечный клиент", value=""
    )
with col2:
    target_broker = st.text_input(
        "Брокер / Посредник", value=""
    )

fuzzy_enabled = st.checkbox("Включить нечёткий поиск (поиск опечаток)", value=False)
semantic_enabled = st.checkbox(
    "Включить семантический ИИ-поиск (искать по смыслу)", value=True
)

if st.button("Начать поиск", type="primary"):
    q = query.strip()
    if not q:
        st.warning("Пожалуйста, введите требования для поиска.")
    else:
        try:
            if semantic_enabled:
                resp = _api_post(
                    "/semantic-match",
                    payload={
                        "query": q,
                        "target_client": target_client.strip(),
                        "target_broker": target_broker.strip(),
                    },
                )
                if resp.ok:
                    _render_search_results(
                        resp.json(),
                        q,
                        target_client=target_client.strip(),
                        target_broker=target_broker.strip(),
                        fuzzy=True,
                    )
                else:
                    st.error(f"Ошибка ИИ-поиска: {resp.status_code}")

            elif fuzzy_enabled:
                keywords = _extract_keywords(q)
                if not keywords:
                    st.warning("Не удалось выделить ключевые слова.")
                else:
                    resp = _api_post(
                        "/fuzzy-match",
                        payload={
                            "keywords": keywords,
                            "target_client": target_client.strip(),
                            "target_broker": target_broker.strip(),
                        },
                    )
                    if resp.ok:
                        _render_search_results(
                            resp.json(),
                            q,
                            target_client=target_client.strip(),
                            target_broker=target_broker.strip(),
                            fuzzy=True,
                        )
                    else:
                        st.error(f"Ошибка нечёткого поиска: {resp.status_code}")

            else:
                resp = _api_get("/search", params={"query": q})
                if resp.ok:
                    _render_search_results(resp.json(), q)
                else:
                    st.error(f"Ошибка классического поиска: {resp.status_code}")
        except Exception as e:
            st.error(f"Не удалось связаться с сервером API: {e}")
