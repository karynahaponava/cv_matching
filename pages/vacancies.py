import os
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PAGE_SIZE = 25


def _api_get(path: str, params: dict | None = None, timeout_s: int = 20) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", params=params, timeout=timeout_s)


def _api_post(path: str, payload: dict | None = None, timeout_s: int = 120) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout_s)


st.set_page_config(page_title="Запросы", layout="wide")

with st.sidebar:
    st.header("Синхронизация запросов")
    st.caption(f"Бэкенд: `{API_BASE}`")

    backfill = st.checkbox("Перезаписать существующие", value=False)
    if st.button("Загрузить из таблицы", use_container_width=True, type="primary"):
        with st.spinner("Загружаю данные из Google Sheets..."):
            try:
                res = requests.post(f"{API_BASE}/sync-vacancies", params={"backfill": backfill}, timeout=120)
                if res.ok:
                    data = res.json()
                    if data.get("status") == "success":
                        stats = data.get("stats", {})
                        st.success(
                            f"Готово! Добавлено: {stats.get('added', 0)}, "
                            f"обновлено: {stats.get('updated', 0)}, "
                            f"пропущено: {stats.get('skipped', 0)}."
                        )
                        st.rerun()
                    else:
                        st.error(f"Ошибка: {data.get('message')}")
                else:
                    st.error(f"Ошибка сервера: {res.status_code}")
            except Exception as e:
                st.error(f"Ошибка подключения к API: {e}")

st.title("Список запросов")
st.markdown("Все вакансии / запросы, загруженные в систему.")

if "vac_page" not in st.session_state:
    st.session_state.vac_page = 1

try:
    res = _api_get("/vacancies", params={"page": st.session_state.vac_page, "page_size": PAGE_SIZE})
    if not res.ok:
        st.error(f"Ошибка сервера: {res.status_code}")
        st.stop()
    data = res.json()
except Exception as e:
    st.error(f"Ошибка подключения к API: {e}")
    st.stop()

total: int = data["total"]
items: list = data["items"]
total_pages = max(1, -(-total // PAGE_SIZE))  # ceiling division

st.caption(f"Всего запросов: **{total}** | Страница {st.session_state.vac_page} из {total_pages}")

if not items:
    st.info("Запросов не найдено.")
else:
    for vac in items:
        with st.container(border=True):
            col_title, col_date = st.columns([5, 2])
            col_title.markdown(f"**{vac['thread_id']}  {vac['title']}**")
            created = vac.get("created_at", "")
            if created:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass
            col_date.caption(f"Добавлено: {created}" if created else "")

            requirements = vac.get("requirements") or ""
            if requirements:
                with st.expander("Требования"):
                    st.markdown(requirements)
            else:
                st.caption("Требования не указаны.")

st.write("---")
nav_cols = st.columns([1, 2, 1])

with nav_cols[0]:
    if st.button("← Назад", disabled=st.session_state.vac_page <= 1, use_container_width=True):
        st.session_state.vac_page -= 1
        st.rerun()

with nav_cols[1]:
    st.markdown(
        f"<div style='text-align:center; padding-top:6px;'>Страница {st.session_state.vac_page} / {total_pages}</div>",
        unsafe_allow_html=True,
    )

with nav_cols[2]:
    if st.button("Вперёд →", disabled=st.session_state.vac_page >= total_pages, use_container_width=True):
        st.session_state.vac_page += 1
        st.rerun()
