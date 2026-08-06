import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PAGE_SIZE = 15

st.set_page_config(page_title="База вакансий", layout="wide")

st.title("🗄️ База сохраненных вакансий")
st.markdown("Просмотр вакансий, собранных авто-парсером или добавленных вручную.")

if "tg_db_page" not in st.session_state:
    st.session_state.tg_db_page = 1

def go_next():
    st.session_state.tg_db_page += 1

def go_prev():
    if st.session_state.tg_db_page > 1:
        st.session_state.tg_db_page -= 1

@st.cache_data(ttl=5, show_spinner=False)
def fetch_vacancies_from_db(page: int, size: int):
    res = requests.get(
        f"{API_BASE}/saved-tg-vacancies", 
        params={"page": page, "page_size": size},
        timeout=10
    )
    res.raise_for_status()
    return res.json()

with st.spinner("Загрузка данных из БД..."):
    try:
        data = fetch_vacancies_from_db(st.session_state.tg_db_page, PAGE_SIZE)
        
        total_items = data.get("total", 0)
        items = data.get("items", [])
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)

        if st.session_state.tg_db_page > total_pages:
            st.session_state.tg_db_page = total_pages

        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            st.button("⬅️ Назад", on_click=go_prev, disabled=(st.session_state.tg_db_page <= 1), use_container_width=True)
        with col_page:
            st.markdown(f"<div style='text-align: center;'><b>Страница {st.session_state.tg_db_page} из {total_pages}</b> (Всего: {total_items})</div>", unsafe_allow_html=True)
        with col_next:
            st.button("Вперед ➡️", on_click=go_next, disabled=(st.session_state.tg_db_page >= total_pages), use_container_width=True)
        
        st.write("---")
        
        if not items:
            st.info("В базе данных пусто.")
        else:
            for post in items:
                with st.container(border=True):
                    st.caption(f"Канал: @{post['channel']} | ID: {post['id']}")
                    
                    st.markdown(f"```text\n{post['text']}\n```")

                    if st.button("🔍 Подобрать кандидатов", key=f"match_{post['id']}", use_container_width=True, type="primary"):
                        st.session_state["search_query_input"] = post['text']
                        st.switch_page("ui.py")
                        
    except requests.exceptions.Timeout:
        st.error("Таймаут: бэкенд не ответил за 10 секунд.")
    except Exception as e:
        st.error(f"Ошибка подключения или обработки: {e}")