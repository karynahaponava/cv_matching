import re
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import requests
import numpy as np
from fastapi import FastAPI, Query, BackgroundTasks
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, or_

from database.db import Base, SessionLocal, engine
from database.models import Candidate, Submission, Vacancy
from services.google_docs import get_doc_text
from services.google_sheets import sync_candidates_from_cloud, sync_vacancies_from_cloud
from services.cv_parser import extract_all_from_text
from services.fuzzy_search import fuzzy_search_candidates
from services.matcher import calculate_match_score
from services.embeddings import embed, cosine_similarity


class ImportExcelRequest(BaseModel):
    filepath: str


class FuzzyMatchRequest(BaseModel):
    keywords: list[str]
    threshold: float = 0.1
    target_client: str = ""
    target_broker: str = ""
    departments: list[str] = []


class SemanticMatchRequest(BaseModel):
    query: str
    target_client: str = ""
    target_broker: str = ""
    departments: list[str] = []


class AnalyzeRequest(BaseModel):
    query: str
    cv_url: str


def update_status(text: str):
    """Helper function for writing the current status to a file"""
    with open("sync_status.txt", "w", encoding="utf-8") as f:
        f.write(text)


def internal_update_cv_texts(days_limit: int = None):
    """Downloading resume texts from Google Docs (optional for the last N days)"""
    session = SessionLocal()
    updated, skipped, errors = 0, 0, 0
    try:
        query = session.query(Candidate).filter(
            or_(
                Candidate.cv_text == None,
                Candidate.cv_text == "",
                func.length(Candidate.cv_text) < 500,
            )
        )
        if days_limit:
            limit_date = datetime.utcnow() - timedelta(days=days_limit)
            query = query.filter(Candidate.created_at >= limit_date)

        candidates = query.all()
        total = len(candidates)
        print(
            f"\n[Парсер CV] Найдено {total} кандидатов для загрузки текста (Лимит дней: {days_limit})..."
        )

        for i, cand in enumerate(candidates, 1):
            if not cand.cv_url or "docs.google.com" not in cand.cv_url:
                skipped += 1
                continue
            print(f"[{i}/{total}] Скачивание CV для: {cand.name[:20]}... ", end="")
            try:
                cv_text = get_doc_text(cand.cv_url)
                if cv_text:
                    cand.cv_text = cv_text
                    updated += 1
                    print("✅ УСПЕШНО")
                else:
                    errors += 1
                    print("❌ ОШИБКА (Документ закрыт)")
            except Exception:
                errors += 1
                print("⚠️ ОШИБКА СЕТИ")

            if i % 10 == 0:
                session.commit()
        session.commit()
        return {"updated": updated, "skipped": skipped, "errors": errors}
    finally:
        session.close()


def internal_parse_cv_stacks(days_limit: int = None):
    """Parsing stack and directions from texts (optional for the last N days)"""
    session = SessionLocal()
    try:
        query = session.query(Candidate).filter(Candidate.cv_text.is_not(None))
        if days_limit:
            limit_date = datetime.utcnow() - timedelta(days=days_limit)
            query = query.filter(Candidate.created_at >= limit_date)

        candidates = query.all()
        updated = 0
        for c in candidates:
            data = extract_all_from_text(c.cv_text)

            c.stack = data["stack"] or c.stack
            c.seniority = data["seniority"] or c.seniority

            if not c.direction or not c.direction.strip():
                c.direction = data["direction"]

            updated += 1

        session.commit()
        print(f"[Парсер стека] Стек и роли успешно обновлены для {updated} кандидатов.")
        return {"updated": updated}
    finally:
        session.close()


def internal_build_embeddings(days_limit: int = None):
    """Generation of AI vectors (optional for the last N days)"""
    session = SessionLocal()
    stats = {"updated": 0, "errors": 0}
    try:
        query = session.query(Candidate).filter(Candidate.embedding.is_(None))
        if days_limit:
            limit_date = datetime.utcnow() - timedelta(days=days_limit)
            query = query.filter(Candidate.created_at >= limit_date)

        candidates = query.all()
        for c in candidates:
            text = f"{c.stack or ''}\n{c.cv_text or ''}".strip()
            if text:
                try:
                    vector = embed(text)
                    c.embedding = np.array(vector, dtype=np.float32).tobytes()
                    stats["updated"] += 1
                except Exception:
                    stats["errors"] += 1
        session.commit()
        return stats
    finally:
        session.close()


def process_cvs_in_background(days_limit: int = None):
    """Full background word processing, parsing and vectorization process"""
    try:
        mode_text = f"за последние {days_limit} дня" if days_limit else "для ВСЕЙ базы"
        update_status(f"Запуск синхронизации ({mode_text}). Шаг 1 завершен.")

        update_status(f"Шаг 2: Скачивание текстов резюме {mode_text}...")
        res_cv = internal_update_cv_texts(days_limit=days_limit)

        update_status(f"Шаг 3: Анализ стека и извлечение направлений {mode_text}...")
        res_stack = internal_parse_cv_stacks(days_limit=days_limit)

        update_status(
            f"Шаг 4: Расчет ИИ-векторов для семантического поиска {mode_text}..."
        )
        res_ai = internal_build_embeddings(days_limit=days_limit)

        update_status("🎉 Синхронизация полностью завершена! Все данные актуальны.")
    except Exception as e:
        update_status(f"❌ Процесс прерван из-за ошибки: {e}")


def nightly_maintenance_job():
    """Automatic nightly build: Updates the structure COMPLETELY, but only parses the last 2 days"""
    print("\n" + "=" * 50)
    print(f"Старт ночного обслуживания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\nШАГ 1: Полная синхронизация структуры и статусов с Excel...")
    session = SessionLocal()
    try:
        stats = sync_candidates_from_cloud(session)
        print(f"✅ Excel синхронизирован: {stats}")
    except Exception as e:
        print(f"❌ Ошибка Excel: {e}")
    finally:
        session.close()

    process_cvs_in_background(days_limit=2)
    print("\n" + "=" * 50 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        nightly_maintenance_job, "cron", hour=1, minute=0, misfire_grace_time=3600
    )
    scheduler.start()
    print("⏰ Планировщик запущен! Единая ночная сборка назначена на 01:00.")
    print("   Правило: Вся таблица Excel ➡️ Дельта за 2 дня (Тексты, Стек, ИИ-векторы)")
    yield
    scheduler.shutdown()
    print("⏰ Планировщик задач остановлен.")


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/sync-excel")
def sync_excel(background_tasks: BackgroundTasks):
    session = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("[Ручной запуск] Шаг 1: Скачивание всей таблицы из Google Sheets...")
        stats = sync_candidates_from_cloud(session)
        print(f"✅ Шаг 1 завершен. Статистика: {stats}")

        background_tasks.add_task(process_cvs_in_background, days_limit=None)

        return {
            "status": "success",
            "message": f"Таблица успешно загружена (Новых: {stats.get('added_candidates', 0)}). Тотальный перепарсинг ВСЕЙ базы и расчет ИИ-векторов запущены!",
        }
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


@app.post("/update-cv-texts")
def update_cv_texts(
    days_limit: int = Query(None, description="Лимит дней для проверки (None = все)")
):
    return internal_update_cv_texts(days_limit=days_limit)


@app.post("/parse-cv-stacks")
def parse_cv_stacks(
    days_limit: int = Query(None, description="Лимит дней для парсинга (None = все)")
):
    return internal_parse_cv_stacks(days_limit=days_limit)


@app.post("/build-embeddings")
def build_embeddings(
    days_limit: int = Query(
        None, description="Лимит дней для генерации эмбеддингов (None = все)"
    )
):
    return internal_build_embeddings(days_limit=days_limit)


@app.post("/fuzzy-match")
def fuzzy_match(request: FuzzyMatchRequest):
    return fuzzy_search_candidates(
        request.keywords,
        request.target_client,
        request.target_broker,
        request.threshold,
    )


@app.post("/semantic-match")
def semantic_match(request: SemanticMatchRequest):
    session = SessionLocal()
    try:
        query_vec = embed(request.query)

        db_query = session.query(Candidate).filter(Candidate.embedding.is_not(None))

        if request.departments:
            db_query = db_query.filter(Candidate.direction.in_(request.departments))

        candidates = db_query.all()

        tc, tb = (
            request.target_client.strip().lower(),
            request.target_broker.strip().lower(),
        )

        from services.fuzzy_search import get_candidate_badge

        matched_cands = []
        for c in candidates:
            c_vec = np.frombuffer(c.embedding, dtype=np.float32).tolist()
            score = cosine_similarity(query_vec, c_vec) * 100
            if score >= 30.0:
                matched_cands.append((c, score))

        if not matched_cands:
            return []

        names = list(set([c.name for c, _ in matched_cands]))
        all_cands = (
            session.query(Candidate.id, Candidate.name, Candidate.cv_url)
            .filter(Candidate.name.in_(names))
            .all()
        )

        name_to_ids, id_to_url = {}, {}
        for c_id, c_name, c_url in all_cands:
            name_to_ids.setdefault(c_name, []).append(c_id)
            id_to_url[c_id] = c_url

        all_ids = [cid for ids in name_to_ids.values() for cid in ids]
        subs = (
            session.query(Submission).filter(Submission.candidate_id.in_(all_ids)).all()
        )

        for s in subs:
            s.cv_url = id_to_url.get(s.candidate_id, "Ссылка не найдена")

        results = []
        for c, score in matched_cands:
            c_ids = name_to_ids.get(c.name, [])
            c_subs = [s for s in subs if s.candidate_id in c_ids]
            badge_color, badge_text = get_candidate_badge(c.id, c_subs, tc, tb)
            results.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "cv_url": c.cv_url,
                    "stack": c.stack,
                    "score": score,
                    "badge_color": badge_color,
                    "badge_text": badge_text,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    finally:
        session.close()


@app.get("/search")
def search(query: str = Query(..., min_length=1)):
    session = SessionLocal()
    try:
        candidates = session.query(Candidate).all()
        results = []
        for c in candidates:
            combined_text = f"{c.stack or ''}\n{c.cv_text or ''}"
            score = calculate_match_score(query, combined_text)
            if score > 0:
                results.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "cv_url": c.cv_url,
                        "stack": c.stack,
                        "score": score,
                    }
                )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    finally:
        session.close()


@app.get("/sync-status")
def get_sync_status():
    if os.path.exists("sync_status.txt"):
        with open("sync_status.txt", "r", encoding="utf-8") as f:
            return {"status": f.read()}
    return {"status": "Синхронизация еще не запускалась"}


@app.post("/analyze-cv")
def analyze_cv(request: AnalyzeRequest):
    from services.embeddings import model, cosine_similarity, embed

    session = SessionLocal()
    try:
        cand = (
            session.query(Candidate)
            .filter(Candidate.cv_url == request.cv_url.strip())
            .first()
        )
        if not cand or not cand.cv_text:
            return {"error": "Кандидат не найден или нет текста резюме"}

        cand_stack = cand.stack or "Стек не распарсился"
        kw_pattern = re.compile(r"[a-zA-Z0-9+#\.\-_/]+")
        query_kws = list(
            dict.fromkeys(
                [w.lower() for w in kw_pattern.findall(request.query) if len(w) >= 2]
            )
        )
        query_stack = ", ".join(query_kws).title() if query_kws else "Не найдено"

        raw_cv_blocks = re.split(r"\n|(?<=[.!?])\s+", cand.cv_text)
        cv_blocks = [b.strip() for b in raw_cv_blocks if len(b.strip()) > 40]
        if not cv_blocks:
            return {"error": "Текст резюме слишком короткий или не читается"}

        cv_vecs = model.encode(cv_blocks).tolist()
        req_lines = [
            line.strip() for line in request.query.split("\n") if len(line.strip()) > 15
        ]
        if len(req_lines) < 2:
            req_lines = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", request.query)
                if len(s.strip()) > 15
            ]
        req_lines = req_lines[:15]

        matches = []
        for req in req_lines:
            req_vec = embed(req)
            best_score = 0
            best_block = ""
            for i, cv_vec in enumerate(cv_vecs):
                score = cosine_similarity(req_vec, cv_vec) * 100
                if score > best_score:
                    best_score = score
                    best_block = cv_blocks[i]
            matches.append(
                {
                    "requirement": req,
                    "cv_match": best_block,
                    "score": round(best_score, 1),
                }
            )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return {
            "query_stack": query_stack,
            "candidate_stack": cand_stack,
            "matches": matches,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        session.close()


@app.post("/sync-vacancies")
def sync_vacancies(backfill: bool = Query(False)):
    session = SessionLocal()
    try:
        stats = sync_vacancies_from_cloud(session, backfill=backfill)
        return {"status": "success", "stats": stats}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


@app.get("/vacancies")
def get_vacancies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    department: str = Query(None),
):
    session = SessionLocal()
    try:
        query = session.query(Vacancy)
        if department:
            query = query.filter(Vacancy.department == department)
        total = query.with_entities(func.count(Vacancy.id)).scalar()
        rows = query.order_by(Vacancy.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": v.id,
                    "thread_id": v.thread_id,
                    "title": v.title,
                    "department": v.department,
                    "requirements": v.requirements,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in rows
            ],
        }
    finally:
        session.close()


@app.get("/vacancy-departments")
def get_vacancy_departments():
    session = SessionLocal()
    try:
        rows = session.query(Vacancy.department).filter(Vacancy.department != "N/A").distinct().all()
        return sorted([r[0] for r in rows])
    finally:
        session.close()


@app.get("/departments")
def get_departments():
    session = SessionLocal()
    try:
        deps = (
            session.query(Candidate.direction)
            .filter(Candidate.direction.is_not(None), Candidate.direction != "")
            .distinct()
            .all()
        )

        return sorted([d[0] for d in deps])
    finally:
        session.close()
