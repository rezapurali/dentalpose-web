from typing import Optional, List
from pydantic import BaseModel


class DoctorCreate(BaseModel):
    name: str


class DoctorOut(BaseModel):
    id: int
    display_name: str
    has_baseline: bool

    class Config:
        from_attributes = True


class BaselineIn(BaseModel):
    hip: float
    knee: float
    neck: float
    chin: float
    shoulder_baseline: float


class BaselineOut(BaseModel):
    hip: float
    knee: float
    neck: float
    chin: float
    shoulder_baseline: float
    calibrated_at: float

    class Config:
        from_attributes = True


class SessionStart(BaseModel):
    doctor_id: int


class SessionOut(BaseModel):
    id: int
    doctor_id: int
    started_at: float

    class Config:
        from_attributes = True


class FrameIn(BaseModel):
    time: float
    hip_angle: float
    knee_angle: float
    neck_angle: float
    chin_angle: float
    shoulder_elev_pct: float
    hip_bad: bool
    knee_bad: bool
    neck_bad: bool
    chin_bad: bool
    shoulder_bad: bool
    is_standing: bool = False


class FrameBatchIn(BaseModel):
    session_id: int
    frames: List[FrameIn]
