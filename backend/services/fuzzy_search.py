from datetime import datetime, timedelta
from sqlalchemy import text
from database.models import Candidate, Submission
from database.db import SessionLocal

from datetime import datetime, timedelta


def get_candidate_badge(current_cv_id, all_subs, tc, tb):
    """
    1. Ищет точное пересечение введённого клиента и введённого брокера.
    2. Если точного совпадения нет, смотрит историю по клиенту.
    3. Если по клиенту чисто, смотрит историю по брокеру.
    """
    if not tc and not tb:
        return None, None

    tc = (tc or "").strip().lower()
    tb = (tb or "").strip().lower()

    exact_subs = []
    client_subs = []
    broker_subs = []

    for s in all_subs:
        c = (s.end_client or "").strip().lower()
        b = (s.intermediary or "").strip().lower()
        st = (s.status or "").strip().lower()

        if st == "skip":
            continue

        if tc and tb and c == tc and b == tb:
            exact_subs.append(s)

        if tc and c == tc:
            client_subs.append(s)

        if tb and b == tb:
            broker_subs.append(s)

    exact_subs.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    client_subs.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    broker_subs.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)

    def get_cv_suffix(sub_obj):
        url = getattr(sub_obj, "cv_url", "") or "ссылка в истории"
        if sub_obj.candidate_id == current_cv_id:
            return " [по этому же резюме]"
        return f" [по резюме: {url}]"

    # ==========================================================
    # КЕЙС 1: Есть ТОЧНОЕ совпадение связки (Клиент + Брокер), которую ищет сейлз
    # ==========================================================
    if exact_subs:
        latest = exact_subs[0]
        result = (latest.request_result or "").strip().lower()
        suffix = get_cv_suffix(latest)

        if result == "succeeded":
            return (
                "red",
                f"Трудоустроен: выведен в {tc.upper()} через брокера {tb.upper()}{suffix}",
            )

        if result in ("failed", "choose other candidate"):
            return (
                "green",
                f"Был отказ от {tc.upper()} через брокера {tb.upper()} — можно переподать{suffix}",
            )

        return (
            "yellow",
            f"Сейчас в процессе в {tc.upper()} через {tb.upper()} — можно переподать{suffix}",
        )

    # ==========================================================
    # КЕЙС 2: Точной связки нет, но кандидат подавался к этому КЛИЕНТУ (через другого брокера)
    # ==========================================================
    if client_subs:
        latest = client_subs[0]
        alt_broker = (latest.intermediary or "напрямую").upper()
        result = (latest.request_result or "").strip().lower()
        suffix = get_cv_suffix(latest)

        if result == "succeeded":
            return (
                "red",
                f"Трудоустроен: успешно выведен в {tc.upper()} (через {alt_broker}){suffix}",
            )

        if result in ("failed", "choose other candidate"):
            target_way = f"через брокера {tb.upper()}" if tb else "напрямую"
            return (
                "green",
                f"Ранее был отказ от {tc.upper()} (подача шла через {alt_broker}) — можно подать {target_way}{suffix}",
            )

        target_way = f"через брокера {tb.upper()}" if tb else "напрямую"
        return (
            "yellow",
            f"Сейчас в процессе в {tc.upper()} через {alt_broker} — можно переподать {target_way}{suffix}",
        )
    # ==========================================================
    # КЕЙС 3: К клиенту не подавался, но есть история работы с этим БРОКЕРОМ
    # ==========================================================
    if broker_subs:
        latest = broker_subs[0]
        alt_client = (latest.end_client or "другой проект").upper()
        result = (latest.request_result or "").strip().lower()
        suffix = get_cv_suffix(latest)

        if result == "succeeded":
            return (
                "red",
                f"Уже трудоустроен через брокера {tb.upper()} на проект {alt_client}",
            )

        return (
            "green",
            f"Работает с {tb.upper()} на проекте {alt_client}. Для {tc.upper()} кандидат чист — можно подать{suffix}",
        )

    # ==========================================================
    # КЕЙС 4: Абсолютно чистый кандидат
    # ==========================================================
    if tc and tb:
        return (
            "green",
            f"Не отправлялся ни в {tc.upper()}, ни через {tb.upper()} — свободен для подачи",
        )
    if tc:
        return "green", f"Не отправлялся в {tc.upper()} — свободен для подачи"
    if tb:
        return (
            "green",
            f"Не отправлялся через {tb.upper()} — свободен для подачи",
        )
    return None, None


def fuzzy_search_candidates(
    keywords: list[str],
    target_client: str = None,
    target_broker: str = None,
    threshold: float = 0.3,
    departments: list[str] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    cleaned = [k.strip().lower() for k in keywords if k and k.strip()]

    cleaned_departments = [
        department.strip()
        for department in (departments or [])
        if department and department.strip()
    ]

    if not cleaned:
        return [], 0

    cte = r"""
        WITH kw AS (
            SELECT unnest(CAST(:keywords AS text[])) AS keyword
        ),
        per_keyword AS (
            SELECT
                c.id, c.name, c.cv_url, c.stack,
                GREATEST(
                    -- Проверка на точное совпадение целого слова (без эффекта Django)
                    CASE WHEN c.stack ~* ('\m' || kw.keyword || '\M') THEN 1.0 ELSE 0.0 END,
                    CASE WHEN c.cv_text ~* ('\m' || kw.keyword || '\M') THEN 1.0 ELSE 0.0 END,
                    -- Нечеткий поиск (прощает опечатки)
                    word_similarity(kw.keyword, lower(COALESCE(c.stack, ''))),
                    word_similarity(kw.keyword, lower(COALESCE(c.cv_text, '')))
                ) AS sim
            FROM candidates c
            CROSS JOIN kw
            WHERE (
                COALESCE(cardinality(CAST(:departments AS text[])), 0) = 0
                OR c.direction = ANY(CAST(:departments AS text[]))
            )
        ),
        aggregated AS (
            SELECT
                id, name, cv_url, stack,
                -- Берем СРЕДНЕЕ совпадение по всем введенным словам, а не максимум
                AVG(sim) AS final_sim
            FROM per_keyword
            GROUP BY id, name, cv_url, stack
        )
    """
    count_sql = text(cte + """
        SELECT COUNT(*)
        FROM aggregated
        WHERE final_sim >= :threshold
    """)
    page_sql = text(cte + """
        SELECT
            a.id, a.name, a.cv_url, a.stack,
            ROUND((a.final_sim * 100)::numeric, 2) AS score
        FROM aggregated a
        WHERE a.final_sim >= :threshold
        ORDER BY a.final_sim DESC, a.id ASC
        LIMIT :limit OFFSET :offset
    """)

    session = SessionLocal()
    try:
        params = {
            "keywords": cleaned,
            "threshold": threshold,
            "departments": cleaned_departments,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        total = int(session.execute(count_sql, params).scalar() or 0)
        rows = (
            session.execute(
                page_sql,
                params,
            )
            .mappings()
            .all()
        )
        if not rows:
            return [], total

        names = list(set([r["name"] for r in rows]))
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
        tc = (target_client or "").strip().lower()
        tb = (target_broker or "").strip().lower()

        for row in rows:
            c_name = row["name"]
            c_ids = name_to_ids.get(c_name, [])
            c_subs = [s for s in subs if s.candidate_id in c_ids]

            badge_color, badge_text = get_candidate_badge(row["id"], c_subs, tc, tb)

            results.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "cv_url": row["cv_url"],
                    "stack": row["stack"],
                    "score": float(row["score"]),
                    "badge_color": badge_color,
                    "badge_text": badge_text,
                }
            )
        return results, total
    finally:
        session.close()
