"""
DentalPose Web — Database Models
همون ساختار نسخه‌ی دسکتاپ (باسلاین جدا هر دکتر، سشن‌ها، فریم‌های پوسچر)،
فقط به‌جای پوشه/CSV روی دیسک، توی دیتابیس مرکزیه — این یعنی هر همکار از
گوشی خودش وصل میشه ولی داده‌ها یه‌جا جمع میشن.
"""
import time
from sqlalchemy import (Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship
from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String, nullable=False)
    folder_key = Column(String, unique=True, index=True, nullable=False)  # نسخه‌ی نرمالایز‌شده برای تطبیق
    created_at = Column(Float, default=time.time)

    baseline = relationship("Baseline", back_populates="doctor", uselist=False)
    sessions = relationship("Session", back_populates="doctor")


class Baseline(Base):
    __tablename__ = "baselines"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), unique=True, nullable=False)
    hip = Column(Float, nullable=False)
    knee = Column(Float, nullable=False)
    neck = Column(Float, nullable=False)
    chin = Column(Float, nullable=False)
    shoulder_baseline = Column(Float, nullable=False)
    calibrated_at = Column(Float, default=time.time)

    doctor = relationship("Doctor", back_populates="baseline")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    started_at = Column(Float, default=time.time)
    ended_at = Column(Float, nullable=True)

    doctor = relationship("Doctor", back_populates="sessions")
    frames = relationship("PostureFrameRow", back_populates="session")


class PostureFrameRow(Base):
    __tablename__ = "posture_frames"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    time = Column(Float, nullable=False)  # unix timestamp، دقیقاً مثل ستون 'time' توی CSV دسکتاپ
    hip_angle = Column(Float)
    knee_angle = Column(Float)
    neck_angle = Column(Float)
    chin_angle = Column(Float)
    shoulder_elev_pct = Column(Float)
    hip_bad = Column(Boolean, default=False)
    knee_bad = Column(Boolean, default=False)
    neck_bad = Column(Boolean, default=False)
    chin_bad = Column(Boolean, default=False)
    shoulder_bad = Column(Boolean, default=False)
    is_standing = Column(Boolean, default=False)

    session = relationship("Session", back_populates="frames")
