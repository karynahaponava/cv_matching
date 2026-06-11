import os
import io
import pandas as pd
import requests
from datetime import datetime

def sync_candidates_from_cloud(session):
    try:
        spreadsheet_url = os.getenv("SPREADSHEET_URL")
        if not spreadsheet_url:
            raise Exception("SPREADSHEET_URL не задан в .env файле")

        response = requests.get(spreadsheet_url, timeout=30)
        df = pd.read_excel(io.BytesIO(response.content))
        df = df.fillna("")

        if "Candidate" not in df.columns or "Link" not in df.columns:
            raise Exception("На вкладке нет колонок 'Candidate' или 'Link'.")

        from models import Candidate, Submission, Vacancy

        added_cand_count = 0
        added_sub_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            cv_url = str(row.get("Link", "")).strip()
            name = str(row.get("Candidate", "")).strip()

            if not cv_url or not name or not cv_url.startswith("http"):
                skipped_count += 1
                continue

            req_title = str(row.get("Request", "")).strip()
            req_desc = str(row.get("Request description", "")).strip()
            combined_stack = f"{req_title} {req_desc}".strip()

            vacancy_id = None
            if req_title:
                vac = session.query(Vacancy).filter(Vacancy.title == req_title).first()
                if not vac:
                    vac = Vacancy(title=req_title, requirements=req_desc)
                    session.add(vac)
                    session.flush()
                vacancy_id = vac.id

            cand = session.query(Candidate).filter(Candidate.cv_url == cv_url).first()
            if not cand:
                cand = Candidate(
                    name=name,
                    cv_url=cv_url,
                    direction=req_title,
                    stack="",
                    seniority="",
                )
                session.add(cand)
                session.flush()
                added_cand_count += 1

            broker = str(row.get("Broker", "")).strip()
            client = str(row.get("Client", "")).strip()
            status = str(row.get("Status", "")).strip()
            req_result = str(row.get("Request result", "")).strip()

            raw_date = row.get("Date")
            submitted_at = None

            if raw_date:
                try:
                    submitted_at = pd.to_datetime(raw_date).to_pydatetime()
                except Exception:
                    submitted_at = None

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

                    if submitted_at:
                        sub.submitted_at = submitted_at
                        updated = True
                    updated = False
                    if db_status != status:
                        sub.status = status
                        updated = True
                    if db_req_result != req_result:
                        sub.request_result = req_result
                        updated = True

                    if updated:
                        added_sub_count += 1
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
            "updated_submissions": added_sub_count,
            "skipped_rows": skipped_count,
        }

    except Exception as e:
        session.rollback()
        raise e
