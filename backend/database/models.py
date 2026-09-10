from datetime import datetime
import pandas as pd
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    LargeBinary,
)

from sqlalchemy.orm import validates
from database.db import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    cv_url = Column(String, unique=True, nullable=False)
    stack = Column(String)
    cv_text = Column(Text)
    seniority = Column(String)
    direction = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    embedding = Column(LargeBinary, nullable=True)
    cv_source_revision = Column(String(128), nullable=True)
    cv_content_hash = Column(String(64), nullable=True)
    parsed_content_hash = Column(String(64), nullable=True)
    parsed_with_version = Column(Integer, nullable=True)
    cv_source_check_failures = Column(Integer, nullable=False, default=0)
    cv_source_next_check_at = Column(DateTime, nullable=True)

    @validates('created_at')
    def validate_created_at(self, key, value):
        if value is None or pd.isna(value) or str(value).strip() in ["", "NaT"]:
            return datetime.utcnow()
        return value


class MaintenanceState(Base):
    __tablename__ = "maintenance_state"

    name = Column(String(64), primary_key=True)
    completed_at = Column(DateTime(timezone=True), nullable=False)


class SyncStatus(Base):
    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(32), nullable=False, unique=True)
    state = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    requirements = Column(Text)
    thread_id = Column(Integer, nullable=False, default=0)
    department = Column(String, nullable=False, default="N/A")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=True)
    intermediary = Column(String, nullable=True)
    end_client = Column(String)
    status = Column(String)
    request_result = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class TelegramVacancy(Base):
    __tablename__ = "telegram_vacancies"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, index=True)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class TelegramChannelState(Base):
    __tablename__ = "telegram_channel_states"
    
    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, unique=True, index=True, nullable=False)
    last_post_id = Column(Integer, default=0, nullable=False)
