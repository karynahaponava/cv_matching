import os
import io
import re
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build


def sync_vacancies_from_cloud(session, backfill: bool = False):
    from database.models import Vacancy

    spreadsheet_url = os.getenv("SPREADSHEET_URL")
    if not spreadsheet_url:
        raise Exception("SPREADSHEET_URL не задан в .env файле")

    match = re.search(r"/d/([a-zA-Z0-9-_]+)", spreadsheet_url)
    if not match:
        raise Exception("Не удалось извлечь ID таблицы из ссылки SPREADSHEET_URL")
    file_id = match.group(1)

    creds_path = os.getenv("GOOGLE_CREDS_PATH")
    if not creds_path:
        raise Exception("GOOGLE_CREDS_PATH не задан в .env файле")

    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    raw_data = (
        service.files()
        .export(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        .execute()
    )

    df = pd.read_excel(io.BytesIO(raw_data)).fillna("")

    if "Request" not in df.columns:
        raise Exception("В таблице нет колонки 'Request'.")

    existing = {
        vac.title: vac for vac in session.query(Vacancy).all()
    }

    added = 0
    updated = 0
    seen = set()
    for _, row in df.iterrows():
        title = str(row.get("Request", "")).strip()
        if not title or title in seen:
            continue
        raw_thread = row.get("Thread", "")
        try:
            thread_id = int(raw_thread)
        except (ValueError, TypeError):
            print(f"[sync_vacancies] Skipping vacancy '{title}': cannot parse Thread value {raw_thread!r} as int")
            continue
        seen.add(title)
        requirements = str(row.get("Request description", "")).strip() or "N/A"
        department = str(row.get("Department", "")).strip() or "N/A"

        if title not in existing:
            session.add(Vacancy(title=title, requirements=requirements, thread_id=thread_id, department=department))
            added += 1
        elif backfill:
            vac = existing[title]
            vac.thread_id = thread_id
            vac.department = department
            vac.requirements = requirements
            updated += 1

    session.commit()
    return {"added": added, "updated": updated, "skipped": len(seen) - added - updated}


def sync_candidates_from_cloud(session):
    try:
        spreadsheet_url = os.getenv("SPREADSHEET_URL")
        if not spreadsheet_url:
            raise Exception("SPREADSHEET_URL не задан в .env файле")

        match = re.search(r"/d/([a-zA-Z0-9-_]+)", spreadsheet_url)
        if not match:
            raise Exception("Не удалось извлечь ID таблицы из ссылки SPREADSHEET_URL")
        file_id = match.group(1)

        creds_path = os.getenv("GOOGLE_CREDS_PATH")
        if not creds_path:
            raise Exception("GOOGLE_CREDS_PATH не задан в .env файле")

        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )

        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        raw_data = (
            service.files()
            .export(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            .execute()
        )

        df = pd.read_excel(io.BytesIO(raw_data))
        df = df.fillna("")

        if "Candidate" not in df.columns or "Link" not in df.columns:
            raise Exception("На вкладке нет колонок 'Candidate' или 'Link'.")

        from database.models import Candidate, Submission, Vacancy

        added_cand_count = 0
        updated_cand_count = 0
        added_sub_count = 0
        updated_sub_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            cv_url = str(row.get("Link", "")).strip()
            name = str(row.get("Candidate", "")).strip()

            if not cv_url or not name or not cv_url.startswith("http"):
                skipped_count += 1
                continue

            req_title = str(row.get("Request", "")).strip()
            req_desc = str(row.get("Request description", "")).strip()
            department = str(row.get("Department", "")).strip()

            raw_date = row.get("Date")
            if pd.isna(raw_date) or not str(raw_date).strip():
                for col_name in row.keys():
                    if str(col_name).strip() == "Date":
                        raw_date = row[col_name]
                        break

            submitted_at = None
            if raw_date:
                try:
                    dt = pd.to_datetime(raw_date, dayfirst=True)
                    if pd.isna(dt):
                        submitted_at = None
                    else:
                        submitted_at = dt.to_pydatetime()
                except Exception as e:
                    print(f"Ошибка парсинга даты '{raw_date}' для {name}: {e}")
                    submitted_at = None

            vacancy_id = None
            if req_title:
                vac = session.query(Vacancy).filter(Vacancy.title == req_title).first()
                if not vac:
                    vac = Vacancy(title=req_title, requirements=req_desc)
                    session.add(vac)
                    session.flush()
                else:
                    if vac.requirements != req_desc:
                        vac.requirements = req_desc
                vacancy_id = vac.id

            cand = session.query(Candidate).filter(Candidate.cv_url == cv_url).first()
            if not cand:
                cand = Candidate(
                    name=name,
                    cv_url=cv_url,
                    direction=department,
                    stack="",
                    seniority="",
                    created_at=submitted_at,
                )
                session.add(cand)
                session.flush()
                added_cand_count += 1
            else:
                cand_updated = False
                if cand.name != name:
                    cand.name = name
                    cand_updated = True
                if cand.direction != department:
                    cand.direction = department
                    cand_updated = True
                if submitted_at and cand.created_at != submitted_at:
                    cand.created_at = submitted_at
                    cand_updated = True

                if cand_updated:
                    updated_cand_count += 1

            broker = str(row.get("Broker", "")).strip()
            client = str(row.get("Client", "")).strip()
            status = str(row.get("Status", "")).strip()
            req_result = str(row.get("Request result", "")).strip()

            if client or broker or vacancy_id:
                sub = (
                    session.query(Submission)
                    .filter(
                        Submission.candidate_id == cand.id,
                        Submission.intermediary == broker,
                        Submission.end_client == client,
                        Submission.vacancy_id == vacancy_id,
                    )
                    .first()
                )

                if sub:
                    db_status = str(sub.status or "").strip()
                    db_req_result = str(sub.request_result or "").strip()

                    sub_updated = False

                    if submitted_at and sub.submitted_at != submitted_at:
                        sub.submitted_at = submitted_at
                        sub_updated = True
                    if db_status != status:
                        sub.status = status
                        sub_updated = True
                    if db_req_result != req_result:
                        sub.request_result = req_result
                        sub_updated = True

                    if sub_updated:
                        updated_sub_count += 1
                else:
                    new_sub = Submission(
                        candidate_id=cand.id,
                        vacancy_id=vacancy_id,
                        intermediary=broker,
                        end_client=client,
                        status=status,
                        request_result=req_result,
                        submitted_at=submitted_at or datetime.utcnow(),
                    )
                    session.add(new_sub)
                    added_sub_count += 1

        session.commit()

        return {
            "added_candidates": added_cand_count,
            "updated_candidates": updated_cand_count,
            "added_submissions": added_sub_count,
            "updated_submissions": updated_sub_count,
            "skipped_rows": skipped_count,
        }

    except Exception as e:
        session.rollback()
        raise e