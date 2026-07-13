"""
DentalPose Web — Database Setup
SQLite برای شروع؛ بعداً با تغییر DATABASE_URL می‌شه رفت روی Postgres بدون
تغییر در models.py یا crud.py (چون از SQLAlchemy استفاده می‌کنیم).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dentalpose.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: ensures models are registered before create_all
    Base.metadata.create_all(bind=engine)
