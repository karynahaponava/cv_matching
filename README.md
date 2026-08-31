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

## DevOps Roadmap

По документу DevOps-часть пока довольно базовая: проект фактически находится на уровне локального прототипа. Стек приложения — **FastAPI + Streamlit + PostgreSQL + Sentence-Transformers + Google APIs**.

### Что непосредственно относится к DevOps

| Направление         | Что сейчас                                        | Что требуется                                                          |
| ------------------- | ------------------------------------------------- | ---------------------------------------------------------------------- |
| **Контейнеризация** | Backend и UI запускаются вручную                  | Dockerize backend/UI + PostgreSQL/pgvector, собрать full-stack Compose |
| **База данных**     | PostgreSQL, embeddings как `LargeBinary`          | Перейти на `pgvector/pgvector:pg16`, включить extension `vector`       |
| **Конфигурация**    | `.env`, `google_creds.json`, Streamlit secrets    | Нормально вынести конфигурацию и секреты из приложения                 |
| **Security/Auth**   | Streamlit доступен без авторизации                | Минимум пароль, лучше JWT через FastAPI                                |
| **Логирование**     | Используются `print()`                            | Structured/standard logging, stdout + при необходимости файл           |
| **Тестирование**    | Автотестов фактически нет                         | pytest + API smoke tests                                               |
| **Background jobs** | Синхронизация запускается вручную и ночью в 01:00 | Надёжно оформить scheduled/background execution                        |
| **Статус job**      | `sync_status.txt` + polling каждые 3 сек          | Перейти на SSE                                                         |
| **Deployment**      | В документе описан localhost                      | Сделать нормальный server deployment                                   |
| **CI/CD**           | Не описан                                         | Фактически отсутствует — нужно проектировать                           |
| **Monitoring**      | Не описан                                         | Фактически отсутствует                                                 |
| **Backup/Recovery** | Не описан                                         | Нужно определить для PostgreSQL                                        |
| **Kubernetes**      | Не заявлен                                        | Для текущего размера проекта не обязателен                             |

Самая явная DevOps-задача из документа — **упаковка всего приложения в Docker**. Авторы прямо пишут, что сейчас backend и UI запускаются вручную в двух терминалах, а целевое состояние — `db + backend + ui` через один `docker-compose`. PostgreSQL предлагается сразу заменить на образ `pgvector/pgvector:pg16`.

### Что я бы выделил как DevOps scope

**1. Dockerization — P0**

Нужно получить примерно такую архитектуру:

```text
                Users
                  │
             Reverse Proxy
                  │
          ┌───────┴───────┐
          │               │
      Streamlit         FastAPI
        :8501             :8000
                            │
                            ▼
                       PostgreSQL
                        + pgvector
```

В самом roadmap Docker full-stack Compose стоит как «желательно / малая сложность», но с DevOps-точки зрения для переноса прототипа на сервер я бы поднял его приоритет: без воспроизводимого runtime дальнейший CI/CD и deployment делать неудобно. Документ предлагает `pgvector/pgvector:pg16`, backend через Uvicorn и Streamlit UI.

**2. Secrets/configuration — P0**

Сейчас фигурируют:

```text
.env
google_creds.json
POSTGRES_PASSWORD
Streamlit secrets.toml
```

Причём ошибка `google_creds.json` прямо указана как одна из причин падения синхронизации.

Для нормального деплоя нужно отделить config от image, исключить credentials из Git и определить механизм передачи Google credentials и DB password.

**3. Авторизация — P0**

Сейчас интерфейс `localhost:8501` вообще не имеет authentication. В документе предлагаются два варианта: простой через Streamlit secrets и более нормальный — **JWT через FastAPI + cookies + роли**.

При выносе приложения на сервер это уже становится инфраструктурно значимым вопросом: TLS, reverse proxy, authentication и ограничение доступа.

**4. Logging / observability — P1**

Сейчас используется `print()`. В roadmap прямо требуется нормальное логирование с timestamp и уровнями `INFO/ERROR`.

Я бы для контейнерного варианта не делал основной упор на `app.log`, а писал application logs в stdout/stderr и уже дальше собирал их инфраструктурным способом.

**5. CI/CD — по сути отсутствует**

В документе есть pytest и Docker, но полноценного pipeline нет. Тестами предполагается покрыть parser, badges, embeddings и smoke-тесты FastAPI endpoint'ов.

DevOps здесь логично сделать:

```text
commit
  ↓
lint / validate
  ↓
pytest
  ↓
docker build
  ↓
image scan
  ↓
push registry
  ↓
deploy dev
  ↓
smoke test
  ↓
deploy prod
```

Это уже **моя рекомендация**, а не требование исходного документа.

### Что отсутствует в документе, но потребуется для production

Документ заканчивает DevOps-инфраструктуру примерно на уровне Docker Compose. В нём **нет требований** к Kubernetes, GitLab CI/GitHub Actions, registry, reverse proxy, TLS, мониторингу, healthchecks, alerting, backup PostgreSQL, rollback, dev/stage/prod environments и управлению секретами уровня Vault.

Поэтому я бы разделил работу на два этапа:

**MVP deployment:** Dockerfiles → Compose → pgvector → `.env`/secrets → reverse proxy + TLS → server deployment → backup PostgreSQL → basic logging → CI build/test/deploy.

**Productionization:** registry → dev/prod environments → proper secrets management → monitoring/alerts → centralized logs → automated backups + restore test → rollback → resource limits → vulnerability scanning.

Причём **Kubernetes сюда тащить пока необязательно**. По описанному масштабу это три основных runtime-компонента (`Streamlit → FastAPI → PostgreSQL`), поэтому нормальный Docker Compose на VM вполне может закрыть первый production deployment. Kubernetes имеет смысл добавлять уже при требованиях по HA, масштабированию, нескольким окружениям или общей корпоративной платформе.

В исходном roadmap непосредственно DevOps-смежными являются **авторизация, SSE, логирование, pytest и Docker full-stack compose**; сам документ оценивает последние три инфраструктурно близкие задачи как относительно небольшие.

Если задача — **оценить работу именно Middle DevOps**, я бы следующим шагом разложил это в формате **Epic → DevOps tasks → часы → зависимости → риски**, отдельно для **MVP и production**.
