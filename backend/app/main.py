"""
DentalPose Web — API Server
"""
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as DBSession
import os

from app.database import get_db, init_db
from app import crud, schemas
from app.report import generate_pdf_bytes, rtl_shaping_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DentalPose Web API")

# CORS باز — چون فرانت‌اند ممکنه از یه دامنه‌ی جدا (GitHub Pages/Render دیگه) سرو بشه
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    if not rtl_shaping_available():
        logger.warning("Persian text shaping libraries missing — PDF reports will render Persian incorrectly")


@app.get("/api/health")
def health():
    return {"status": "ok", "rtl_available": rtl_shaping_available()}


# ---------------------------------------------------------
# دکتر / پروفایل
# ---------------------------------------------------------
@app.post("/api/doctors", response_model=schemas.DoctorOut)
def create_or_get_doctor(payload: schemas.DoctorCreate, db: DBSession = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name cannot be empty")
    doctor = crud.get_or_create_doctor(db, name)
    baseline = crud.get_baseline(db, doctor.id)
    return schemas.DoctorOut(id=doctor.id, display_name=doctor.display_name, has_baseline=baseline is not None)


# ---------------------------------------------------------
# باسلاین
# ---------------------------------------------------------
@app.get("/api/doctors/{doctor_id}/baseline", response_model=schemas.BaselineOut)
def get_baseline(doctor_id: int, db: DBSession = Depends(get_db)):
    baseline = crud.get_baseline(db, doctor_id)
    if not baseline:
        raise HTTPException(404, "No baseline found")
    return baseline


@app.post("/api/doctors/{doctor_id}/baseline", response_model=schemas.BaselineOut)
def save_baseline(doctor_id: int, payload: schemas.BaselineIn, db: DBSession = Depends(get_db)):
    doctor = crud.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(404, "Doctor not found")
    return crud.save_baseline(db, doctor_id, payload)


# ---------------------------------------------------------
# سشن‌ها و فریم‌ها
# ---------------------------------------------------------
@app.post("/api/sessions", response_model=schemas.SessionOut)
def start_session(payload: schemas.SessionStart, db: DBSession = Depends(get_db)):
    doctor = crud.get_doctor(db, payload.doctor_id)
    if not doctor:
        raise HTTPException(404, "Doctor not found")
    return crud.start_session(db, payload.doctor_id)


@app.post("/api/sessions/{session_id}/end")
def end_session(session_id: int, db: DBSession = Depends(get_db)):
    session = crud.end_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"status": "ended"}


@app.post("/api/frames")
def add_frames(payload: schemas.FrameBatchIn, db: DBSession = Depends(get_db)):
    if not payload.frames:
        return {"saved": 0}
    crud.add_frames(db, payload.session_id, payload.frames)
    return {"saved": len(payload.frames)}


# ---------------------------------------------------------
# گزارش PDF
# ---------------------------------------------------------
@app.get("/api/doctors/{doctor_id}/report.pdf")
def get_report(doctor_id: int, db: DBSession = Depends(get_db)):
    doctor = crud.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(404, "Doctor not found")
    frames = crud.get_all_frames_for_doctor(db, doctor_id)
    pdf_bytes = generate_pdf_bytes(doctor.display_name, frames)
    if pdf_bytes is None:
        raise HTTPException(404, "No tracked data yet for this doctor")
    safe_name = "".join(c if c.isalnum() else "_" for c in doctor.display_name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_DentalPose_Report.pdf"'},
    )


# ---------------------------------------------------------
# فایل‌های استاتیک فرانت‌اند (اختیاری — اگه فرانت‌اند از همین سرور سرو بشه)
# ---------------------------------------------------------
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
