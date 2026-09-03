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

### Локальная разработка

Для локальной разработки используйте отдельный Compose без nginx, TLS и certbot:

```bash
cd infra
docker compose -f docker-compose.local.yml up --build
```

Local Compose запускает:

- PostgreSQL на `localhost:5432`;
- FastAPI с hot reload на `http://localhost:8000`;
- Streamlit с автоматическим обновлением на `http://localhost:8501`;
- Swagger UI на `http://localhost:8000/docs`.

По умолчанию локальный пароль PostgreSQL — `postgres`. Его и публикуемые порты можно переопределить в `infra/.env`:

```env
POSTGRES_PASSWORD=local-secret
POSTGRES_PORT=5432
BACKEND_PORT=8000
FRONTEND_PORT=8501
SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/...
TG_CHANNELS=https://t.me/channel_1,https://t.me/channel_2
```

Backend local-образ использует CPU-only PyTorch и не скачивает NVIDIA/CUDA-пакеты. Исходники backend и frontend подключены как volumes, поэтому после первой сборки изменения Python-файлов не требуют пересборки образов. Модель Sentence Transformers сохраняется в отдельном Docker volume `huggingface_cache`.

Остановить окружение:

```bash
docker compose -f docker-compose.local.yml down
```

Удалить также локальную БД и кэш модели:

```bash
docker compose -f docker-compose.local.yml down --volumes
```

Последняя команда необратимо удаляет данные локальной PostgreSQL.

## API

После запуска интерактивная документация доступна по адресам:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

### Формат ошибок

Все API endpoints возвращают ошибки в едином JSON-формате:

```json
{
  "code": "SYNC_FAILED",
  "message": "Не удалось выполнить синхронизацию",
  "details": null,
  "trace_id": "3997809c-45ff-4d7e-8071-5f45d49a9678"
}
```

Поля ответа:

| Поле | Тип | Описание |
| --- | --- | --- |
| `code` | `string` | Стабильный машинный код ошибки для клиентской логики |
| `message` | `string` | Безопасное человекочитаемое описание ошибки |
| `details` | `object`, `array` или `null` | Дополнительные данные, например список ошибок валидации |
| `trace_id` | `string` | Идентификатор запроса для поиска события в серверных логах |

`trace_id` также возвращается в HTTP-заголовке `X-Trace-ID`. Внутренние исключения и чувствительные данные не включаются в публичный ответ.

### HTTP-коды ошибок

| HTTP-код | Когда возвращается | Примеры `code` |
| --- | --- | --- |
| `400 Bad Request` | Запрос формально корректен, но содержит пустое или недопустимое значение | `INVALID_REQUEST`, `INVALID_SEARCH_QUERY` |
| `404 Not Found` | Кандидат, endpoint или другой ресурс не найден | `CANDIDATE_NOT_FOUND`, `RESOURCE_NOT_FOUND` |
| `409 Conflict` | Операция конфликтует с текущим состоянием | `SYNC_IN_PROGRESS` |
| `422 Unprocessable Entity` | Тело запроса или query-параметры не прошли валидацию | `VALIDATION_ERROR`, `CV_TEXT_UNPROCESSABLE` |
| `429 Too Many Requests` | Внутренний или внешний сервис ограничил частоту запросов | `RATE_LIMIT_EXCEEDED` |
| `500 Internal Server Error` | Непредвиденная внутренняя ошибка приложения | `INTERNAL_ERROR`, `SEARCH_FAILED`, `SYNC_FAILED` |
| `502 Bad Gateway` | Внешний сервис вернул ошибку или соединение с ним не установлено | `SYNC_FAILED`, `VACANCY_SYNC_FAILED` |
| `504 Gateway Timeout` | Внешний сервис не ответил за отведённое время | `SYNC_FAILED`, `VACANCY_SYNC_FAILED` |

Пример ошибки валидации:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Запрос не прошёл валидацию",
  "details": [
    {
      "type": "missing",
      "loc": ["body", "query"],
      "msg": "Field required",
      "input": {}
    }
  ],
  "trace_id": "3a7778dc-fb95-4fb6-afcb-49bf1dfcd257"
}
```

### Поиск и пагинация

`/semantic-match`, `/fuzzy-match`, `/search`, `/vacancies` и
`/saved-tg-vacancies` возвращают единый ответ:

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 0,
    "total_pages": 0
  }
}
```

Размер страницы по умолчанию — 50, максимум — 100. Для POST-поисков `page` и
`page_size` передаются в JSON body, для GET — в query string. `query` ограничен
2000 символами, fuzzy-поиск принимает до 30 keywords длиной до 64 символов и
до 10 отделов. Лимиты по IP: 30 fuzzy- и 10 semantic-запросов в минуту.

Пустой результат поиска не является ошибкой и возвращается как `200 OK` с
пустым `items` и `total_pages: 0`.

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
