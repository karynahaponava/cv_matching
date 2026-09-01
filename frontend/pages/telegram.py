import os
import requests
import streamlit as st
from dotenv import load_dotenv
from api_client import api_error_message

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
tg_channels_raw = os.getenv("TG_CHANNELS", "")
default_channels = list(dict.fromkeys([ch.strip() for ch in tg_channels_raw.split(",") if ch.strip()]))

st.set_page_config(page_title="Парсер ТГК", layout="wide")

st.title("📡 Ручной парсер Telegram-каналов")
st.markdown("Сбор свежих вакансий из ТГ-каналов в реальном времени.")

if "tg_posts" not in st.session_state:
    st.session_state.tg_posts = []

with st.container(border=True):
    st.subheader("Настройки парсинга")

    col1, col2 = st.columns([3, 1])
    
    with col1:
        channel_option = st.selectbox(
            "Выберите канал из списка (из .env):", 
            options=["Ввести ссылку вручную..."] + default_channels
        )
        
        if channel_option == "Ввести ссылку вручную...":
            channel_url = st.text_input("Введите ссылку на канал:")
        else:
            channel_url = channel_option

    with col2:
        posts_limit = st.number_input("Сколько постов проверить:", min_value=1, max_value=200, value=30, step=10)

    if st.button("Выгрузить вакансии", type="primary", use_container_width=True):
        if not channel_url:
            st.warning("Пожалуйста, укажите ссылку на канал.")
        else:
            with st.spinner(f"Подключаемся к {channel_url}..."):
                try:
                    res = requests.post(
                        f"{API_BASE}/parse-tg",
                        json={"url": channel_url, "limit": posts_limit},
                        timeout=60
                    )
                    
                    if res.ok:
                        data = res.json()
                        if data.get("status") == "success":
                            posts = data.get('posts', [])
                            st.session_state.tg_posts = posts
                            
                            if not posts:
                                st.warning("Парсер отработал, но вернул 0 постов. Возможно, Телеграм временно ограничил доступ (429) или посты слишком короткие.")
                        else:
                            st.error(f"Ошибка парсера: {data.get('detail')}")
                    else:
                        st.error(api_error_message(res, "Ошибка парсера Telegram"))
                except Exception as e:
                    st.error(f"Ошибка подключения: {e}")

if st.session_state.tg_posts:
    st.success(f"Найдено постов: {len(st.session_state.tg_posts)}")
    
    for idx, post in enumerate(st.session_state.tg_posts):
        with st.expander(f"Пост #{idx + 1} из @{post.get('channel', 'канала')}"):
            st.text_area("Текст оригинала", post['text'], height=200, disabled=True, key=f"text_{idx}")
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("Сохранить в БД", key=f"save_{idx}", use_container_width=True):
                    with st.spinner("Сохраняем..."):
                        try:
                            save_res = requests.post(
                                f"{API_BASE}/save-tg-vacancy",
                                json={"channel": post['channel'], "text": post['text']}
                            )
                            if save_res.ok:
                                save_data = save_res.json()
                                if save_data.get("status") == "success":
                                    st.success("Успешно сохранено!")
                                else:
                                    st.info("Уже есть в базе.")
                            else:
                                st.error(
                                    api_error_message(
                                        save_res,
                                        "Не удалось сохранить вакансию",
                                    )
                                )
                        except Exception as e:
                            st.error(f"Ошибка: {e}")
                            
            with col_btn2:
                if st.button("Подобрать кандидатов", key=f"match_{idx}", use_container_width=True):
                    st.session_state["search_query_input"] = post['text']
                    st.switch_page("ui.py")
