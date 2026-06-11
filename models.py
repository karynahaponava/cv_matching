from datetime import datetime

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

from db import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    cv_url = Column(String, unique=True, nullable=False)
    stack = Column(String)
    cv_text = Column(Text)
    seniority = Column(String)
    direction = Column(String)
    rate = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    embedding = Column(LargeBinary, nullable=True)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    requirements = Column(Text)
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
