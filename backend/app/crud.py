"""
DentalPose Web — CRUD operations
منطق نرمالایز‌کردن اسم دکتر دقیقاً همون الگوی نسخه‌ی دسکتاپه (case/whitespace-insensitive)
تا "Reza" و "reza " به یه پروفایل برسن.
"""
import time
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app import models


def _folder_key(name: str) -> str:
    return ' '.join(name.strip().split()).lower()


def get_or_create_doctor(db: DBSession, name: str) -> models.Doctor:
    key = _folder_key(name)
    doctor = db.query(models.Doctor).filter(models.Doctor.folder_key == key).first()
    if doctor:
        return doctor
    doctor = models.Doctor(display_name=name.strip(), folder_key=key)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def get_doctor(db: DBSession, doctor_id: int) -> Optional[models.Doctor]:
    return db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()


def get_baseline(db: DBSession, doctor_id: int) -> Optional[models.Baseline]:
    return db.query(models.Baseline).filter(models.Baseline.doctor_id == doctor_id).first()


def save_baseline(db: DBSession, doctor_id: int, data) -> models.Baseline:
    existing = get_baseline(db, doctor_id)
    if existing:
        existing.hip = data.hip
        existing.knee = data.knee
        existing.neck = data.neck
        existing.chin = data.chin
        existing.shoulder_baseline = data.shoulder_baseline
        existing.calibrated_at = time.time()
        db.commit()
        db.refresh(existing)
        return existing
    baseline = models.Baseline(
        doctor_id=doctor_id, hip=data.hip, knee=data.knee, neck=data.neck,
        chin=data.chin, shoulder_baseline=data.shoulder_baseline, calibrated_at=time.time(),
    )
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    return baseline


def start_session(db: DBSession, doctor_id: int) -> models.Session:
    session = models.Session(doctor_id=doctor_id, started_at=time.time())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def end_session(db: DBSession, session_id: int):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if session:
        session.ended_at = time.time()
        db.commit()
    return session


def add_frames(db: DBSession, session_id: int, frames: list):
    rows = [
        models.PostureFrameRow(
            session_id=session_id, time=f.time,
            hip_angle=f.hip_angle, knee_angle=f.knee_angle, neck_angle=f.neck_angle,
            chin_angle=f.chin_angle, shoulder_elev_pct=f.shoulder_elev_pct,
            hip_bad=f.hip_bad, knee_bad=f.knee_bad, neck_bad=f.neck_bad,
            chin_bad=f.chin_bad, shoulder_bad=f.shoulder_bad, is_standing=f.is_standing,
        )
        for f in frames
    ]
    db.bulk_save_objects(rows)
    db.commit()


def get_all_frames_for_doctor(db: DBSession, doctor_id: int):
    """همه‌ی فریم‌های همه‌ی سشن‌های یه دکتر، برای گزارش PDF"""
    return (
        db.query(models.PostureFrameRow)
        .join(models.Session, models.PostureFrameRow.session_id == models.Session.id)
        .filter(models.Session.doctor_id == doctor_id)
        .order_by(models.PostureFrameRow.time)
        .all()
    )


def count_sessions(db: DBSession, doctor_id: int) -> int:
    return db.query(models.Session).filter(models.Session.doctor_id == doctor_id).count()
