# CV Matching
Система для автоматизации работы сейлзов: парсинг резюме из Google Docs, семантический поиск по ИИ-векторам и учёт истории подач.
## Stack
**UI:** Streamlit
**Backend:** FastAPI, Python
**БД:** PostgreSQL
**Семантический поиск:** Sentence-Transformers
**Инфраструктура:**
- Cloud: Yandex Cloud
- Helm
- K8S
- ArgoCD
- GHCR
- GitHub Actions
- Trivy
- cert-manager
- Terraform
- Docker
## Project Structure (Структура проекта)
```
cv_matching/
├── backend/     — FastAPI-сервер, база данных, бизнес-логика
├── frontend/    — Streamlit UI
├── infra/       — docker-compose, конфигурация Postgres
└── google_creds.json — ключ сервисного аккаунта Google (в корне)
```
## Prerequisites (Необходимые инструменты)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git
## Download and Settings (Установка и настройка)
**1. Клонируйте репозиторий:**
```bash
git clone <ссылка_на_твой_репозиторий>
cd cv_matching
```
**2. Запустите проект:**
```bash
cd infra
sudo docker compose up --build
```
_(база данных, таблицы и все сервисы поднимутся автоматически)_
Сайт откроется на `http://localhost:8501`, API — на `http://localhost:8000`.
