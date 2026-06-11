import re
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import requests
import numpy as np
from fastapi import FastAPI, Query, BackgroundTasks
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from db import Base, SessionLocal, engine
from models import Candidate, Submission, Vacancy
from google_docs import get_doc_text
from google_sheets import sync_candidates_from_cloud
from cv_parser import extract_all_from_text
from fuzzy_search import fuzzy_search_candidates
from matcher import calculate_match_score
from embeddings import embed, cosine_similarity


class ImportExcelRequest(BaseModel):
    filepath: str


class FuzzyMatchRequest(BaseModel):
    keywords: list[str]
    threshold: float = 0.1
    target_client: str = ""
    target_broker: str = ""


class SemanticMatchRequest(BaseModel):
    query: str
    target_client: str = ""
    target_broker: str = ""


def nightly_maintenance_job():
    """A single task that runs all processes strictly in sequence"""
    print("\n" + "=" * 50)
    print(f"Старт ночного обслуживания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\nШАГ 1: Синхронизация с Excel...")
    session = SessionLocal()
    try:
        stats = sync_candidates_from_cloud(session)
        print(f"✅ Excel синхронизирован: {stats}")
    except Exception as e:
        print(f"❌ Ошибка Excel: {e}")
    finally:
        session.close()

    print("\nШАГ 2: Скачивание текстов для новых CV (за 2 дня)...")
    try:
        res_cv = update_cv_texts()
        print(f"✅ Статус скачивания CV: {res_cv}")
    except Exception as e:
        print(f"❌ Ошибка загрузки CV: {e}")

    print("\nШАГ 3: Парсинг стека технологий из новых текстов...")
    try:
        res_stack = parse_cv_stacks()
        print(f"✅ Статус парсинга: {res_stack}")
    except Exception as e:
        print(f"❌ Ошибка парсинга стека: {e}")

    print("\nШАГ 4: Генерация ИИ-векторов для семантического поиска...")
    try:
        stats_ai = build_embeddings()
        print(f"✅ Векторы обновлены: {stats_ai}")
    except Exception as e:
        print(f"❌ Ошибка векторизации: {e}")

    print("\n" + "=" * 50)
    print(
        f"Обслуживание успешно завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 50 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    scheduler = BackgroundScheduler()

    scheduler.add_job(nightly_maintenance_job, "cron", hour=4, minute=00)

    scheduler.start()
    print("⏰ Планировщик запущен! Единая ночная сборка назначена на 04:00.")
    print("   Очередь: Excel ➡️ Скачивание CV ➡️ Парсинг стека ➡️ Векторы ИИ")

    yield

    scheduler.shutdown()
    print("⏰ Планировщик задач остановлен.")


app = FastAPI(lifespan=lifespan)


def extract_gdoc_id(url: str):
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    return match.group(1) if match else None


@app.get("/")
def root():
    return {"status": "ok"}


def process_cvs_in_background():
    """Фоновая задача только для тяжелой работы: скачивание текстов, парсинг и нейросеть"""
    session = SessionLocal()
    try:
        print("\n[Фоновая задача] Шаг 2: Скачивание текстов доступных CV...")
        candidates = session.query(Candidate).filter(
            (Candidate.cv_text == None) | (Candidate.cv_text == "")
        ).all()
        
        total_cvs = len(candidates)
        updated_texts = 0
        for i, cand in enumerate(candidates, 1):
            if not cand.cv_url or "docs.google.com" not in cand.cv_url:
                continue
            
            print(f" [{i}/{total_cvs}] Скачивание CV для: {cand.name}...", end="", flush=True)
            try:
                cv_text = get_doc_text(cand.cv_url)
                if cv_text:
                    cand.cv_text = cv_text
                    updated_texts += 1
                    print(" ✅ УСПЕШНО")
                else:
                    print(" ❌ ОШИБКА (Документ закрыт)")
            except Exception as e:
                print(f" ⚠️ ИСКЛЮЧЕНИЕ СЕТИ: {e}")
                continue
        
        session.commit()
        print(f"✅ Шаг 2 завершен. Успешно скачано: {updated_texts}")

        print("\n[Фоновая задача] Шаг 3: Извлечение стека только из текста резюме...")
        all_candidates = session.query(Candidate).filter(
            Candidate.cv_text.is_not(None),
            Candidate.cv_text != ""
        ).all()
        
        parsed_stacks = 0
        for c in all_candidates:
            data = extract_all_from_text(c.cv_text)
            if data["stack"] and data["stack"].strip():
                c.stack = data["stack"]
                c.seniority = data["seniority"] or c.seniority
                c.direction = data["direction"] or c.direction
                parsed_stacks += 1
            else:
                c.stack = "Стек не распознан (требуется ручная проверка)"
                
        session.commit()
        print(f"✅ Шаг 3 завершен. Обновлено стеков: {parsed_stacks}")
        
        print("\n[Фоновая задача] Шаг 4: Обновление ИИ-векторов...")
        candidates_to_embed = session.query(Candidate).all()
        embed_stats = {"updated": 0}
        
        for c in candidates_to_embed:
            text_to_embed = f"{c.stack or ''}\n{c.cv_text or ''}".strip()
            if text_to_embed:
                try:
                    vector = embed(text_to_embed)
                    c.embedding = np.array(vector, dtype=np.float32).tobytes()
                    embed_stats["updated"] += 1
                except Exception:
                    pass
                
        session.commit()
        print(f"✅ Шаг 4 завершен. Обновлено векторов: {embed_stats['updated']}")
        print("\n" + "=" * 60)
        print("[Фоновая задача] Все шаги успешно выполнены!")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА В ФОНЕ: {e}")
    finally:
        session.close()


@app.post("/sync-excel")
def sync_excel(background_tasks: BackgroundTasks):
    session = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("[Синхронизация] Шаг 1: Скачивание строк из Google Sheets...")
        stats = sync_candidates_from_cloud(session)
        print(f"✅ Шаг 1 завершен. Статистика: {stats}")

        background_tasks.add_task(process_cvs_in_background)

        return {
            "status": "success", 
            "message": f"Таблица успешно загружена (Новых кандидатов: {stats.get('added_candidates', 0)}). Обработка резюме и ИИ-поиска запущена в фоновом режиме!"
        }
    except Exception as e:
        session.rollback()
        print(f"\n❌ ОШИБКА ДОСТУПА ИЛИ СКАЧИВАНИЯ: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


@app.post("/update-cv-texts")
def update_cv_texts():
    session = SessionLocal()
    updated = 0
    skipped = 0
    errors = 0

    try:
        two_days_ago = datetime.utcnow() - timedelta(days=2)
        candidates = (
            session.query(Candidate)
            .filter(
                (Candidate.cv_text == None) | (Candidate.cv_text == ""),
                Candidate.created_at >= two_days_ago,
            )
            .all()
        )

        total = len(candidates)
        print(f"\n[Парсер CV] Найдено {total} новых кандидатов за 2 дня без текста. Начинаю загрузку...")

        for i, cand in enumerate(candidates, 1):
            if not cand.cv_url or "docs.google.com" not in cand.cv_url:
                skipped += 1
                continue

            try:
                cv_text = get_doc_text(cand.cv_url)

                if cv_text:
                    cand.cv_text = cv_text
                    updated += 1
                    print(f"[{i}/{total}] ✅ Успешно скачан текст: {cand.name}")
                else:
                    errors += 1
                    print(f"[{i}/{total}] ❌ Документ закрыт: {cand.name}")
            except Exception as e:
                errors += 1
                print(f"[{i}/{total}] ⚠️ Ошибка сети: {cand.name}")

            if i % 10 == 0:
                session.commit()

        session.commit()
        print(f"\n[Парсер CV] Завершено! Скачано: {updated}, Ошибок: {errors}, Пропущено: {skipped}")

        return {
            "status": "success",
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


@app.post("/parse-cv-stacks")
def parse_cv_stacks(use_llm: bool = False):
    """Regex analysis of resume texts and automatic stack and grade completion"""
    session = SessionLocal()
    try:
        candidates = (
            session.query(Candidate).filter(Candidate.cv_text.is_not(None)).all()
        )

        updated = 0
        for c in candidates:
            data = extract_all_from_text(c.cv_text)

            c.stack = data["stack"] or c.stack
            c.seniority = data["seniority"] or c.seniority
            c.direction = data["direction"] or c.direction

            updated += 1

        session.commit()
        print(f"[Парсер стека] Стек успешно обновлен для {updated} кандидатов.")
        return {"updated": updated}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@app.post("/fuzzy-match")
def fuzzy_match(request: FuzzyMatchRequest):
    """SQL search (word_similarity) with support for endings and typos"""
    return fuzzy_search_candidates(
        request.keywords,
        request.target_client,
        request.target_broker,
        request.threshold,
    )


@app.post("/build-embeddings")
def build_embeddings():
    """Generating AI vectors for semantic search"""
    session = SessionLocal()
    stats = {"updated": 0, "errors": 0}
    try:
        candidates = (
            session.query(Candidate).filter(Candidate.embedding.is_(None)).all()
        )
        for c in candidates:
            text = f"{c.stack or ''}\n{c.cv_text or ''}".strip()
            if text:
                vector = embed(text)
                c.embedding = np.array(vector, dtype=np.float32).tobytes()
                stats["updated"] += 1
        session.commit()
    except Exception as e:
        session.rollback()
        stats["errors"] += 1
    finally:
        session.close()
    return stats


@app.post("/semantic-match")
def semantic_match(request: SemanticMatchRequest):
    """AI search with strict duplicate checking by name and specific resume"""
    session = SessionLocal()
    try:
        query_vec = embed(request.query)
        candidates = (
            session.query(Candidate).filter(Candidate.embedding.is_not(None)).all()
        )

        tc = request.target_client.strip().lower()
        tb = request.target_broker.strip().lower()
        from fuzzy_search import get_candidate_badge

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

        name_to_ids = {}
        id_to_url = {} 
        
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
    """Legacy classic search (left for backward compatibility)"""
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
