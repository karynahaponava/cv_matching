import os
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Лаборатория ИИ", layout="wide")

st.title("Детальный разбор кандидата")
st.markdown("Здесь мы построчно сравниваем  требования с текстом резюме кандидата.")

query = st.text_area("Введите ваш поисковый запрос (вакансию/требования):", height=150)
cv_url = st.text_input("Ссылка на резюме кандидата (которую выдал поиск):", value="")

if st.button("Сравнить кандидата с вакансией", type="primary"):
    if query and cv_url:
        with st.spinner("ИИ анализирует каждую строчку..."):
            try:
                res = requests.post(
                    f"{API_BASE}/analyze-cv",
                    json={"query": query, "cv_url": cv_url.strip()},
                )

                if res.ok:
                    data = res.json()
                    if "error" in data:
                        st.error(data["error"])
                    else:
                        st.write("---")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.info("**Стек из вашего запроса:**")
                            st.write(data["query_stack"])
                        with col2:
                            st.success("**Стек кандидата (из базы):**")
                            st.write(data["candidate_stack"])

                        st.write("---")
                        st.subheader("Построчное совпадение требований")
                        st.markdown(
                            "ИИ разбил вашу вакансию на логические строки и нашел **наиболее подходящие фразы** в резюме для каждой из них."
                        )

                        for match in data["matches"]:
                            score = match["score"]
                            if score >= 60:
                                color = "🟢"
                            elif score >= 40:
                                color = "🟡"
                            else:
                                color = "🔴"

                            with st.container(border=True):
                                st.markdown(
                                    f"**Требование из вакансии:**\n> {match['requirement']}"
                                )
                                st.markdown(
                                    f"**{color} Найдено в резюме (Совпадение {score}%):**\n*{match['cv_match']}*"
                                )

                else:
                    st.error(f"Ошибка сервера: {res.status_code}")
            except Exception as e:
                st.error(f"Ошибка подключения: {e}")
    else:
        st.warning("Пожалуйста, заполните оба поля.")
