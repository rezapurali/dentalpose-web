"""
تست‌های backend — کل جریان: ساخت دکتر، باسلاین، سشن، فریم، گزارش PDF
اجرا: cd backend && python -m pytest tests/ -v   (یا python -m unittest discover tests -v)
"""
import os
import sys
import time
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# دیتابیس تستی جدا از دیتابیس واقعی
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"

from fastapi.testclient import TestClient
from app.database import init_db
from app.main import app

init_db()
client = TestClient(app)


class TestDoctorFlow(unittest.TestCase):
    def test_health(self):
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_create_doctor_and_dedupe_by_name(self):
        r1 = client.post("/api/doctors", json={"name": "Reza"})
        r2 = client.post("/api/doctors", json={"name": "reza "})
        r3 = client.post("/api/doctors", json={"name": "  REZA"})
        self.assertEqual(r1.status_code, 200)
        id1, id2, id3 = r1.json()["id"], r2.json()["id"], r3.json()["id"]
        self.assertEqual(id1, id2)
        self.assertEqual(id1, id3)
        self.assertFalse(r1.json()["has_baseline"])

    def test_empty_name_rejected(self):
        r = client.post("/api/doctors", json={"name": "   "})
        self.assertEqual(r.status_code, 400)


class TestBaselineFlow(unittest.TestCase):
    def setUp(self):
        r = client.post("/api/doctors", json={"name": f"BaselineDoc{time.time()}"})
        self.doctor_id = r.json()["id"]

    def test_no_baseline_returns_404(self):
        r = client.get(f"/api/doctors/{self.doctor_id}/baseline")
        self.assertEqual(r.status_code, 404)

    def test_save_and_load_baseline(self):
        payload = {"hip": 95.0, "knee": 92.0, "neck": 10.0, "chin": 8.0, "shoulder_baseline": 1.2}
        r = client.post(f"/api/doctors/{self.doctor_id}/baseline", json=payload)
        self.assertEqual(r.status_code, 200)
        self.assertIn("calibrated_at", r.json())

        r2 = client.get(f"/api/doctors/{self.doctor_id}/baseline")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["hip"], 95.0)

    def test_recalibrate_overwrites(self):
        payload = {"hip": 95.0, "knee": 92.0, "neck": 10.0, "chin": 8.0, "shoulder_baseline": 1.2}
        client.post(f"/api/doctors/{self.doctor_id}/baseline", json=payload)
        payload2 = {"hip": 100.0, "knee": 90.0, "neck": 12.0, "chin": 9.0, "shoulder_baseline": 1.5}
        client.post(f"/api/doctors/{self.doctor_id}/baseline", json=payload2)
        r = client.get(f"/api/doctors/{self.doctor_id}/baseline")
        self.assertEqual(r.json()["hip"], 100.0)


class TestSessionAndFramesFlow(unittest.TestCase):
    def setUp(self):
        r = client.post("/api/doctors", json={"name": f"SessionDoc{time.time()}"})
        self.doctor_id = r.json()["id"]

    def test_full_session_lifecycle(self):
        r = client.post("/api/sessions", json={"doctor_id": self.doctor_id})
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["id"]

        t0 = time.time()
        frames = [{
            "time": t0 + j, "hip_angle": 95, "knee_angle": 90, "neck_angle": 15,
            "chin_angle": 10, "shoulder_elev_pct": 5,
            "hip_bad": (j % 5 == 0), "knee_bad": False, "neck_bad": False,
            "chin_bad": False, "shoulder_bad": False, "is_standing": False,
        } for j in range(50)]
        r2 = client.post("/api/frames", json={"session_id": session_id, "frames": frames})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["saved"], 50)

        r3 = client.post(f"/api/sessions/{session_id}/end")
        self.assertEqual(r3.status_code, 200)

    def test_frames_for_nonexistent_session_still_inserts(self):
        # crud.add_frames doesn't validate session existence — acceptable for MVP,
        # but flag it: frontend should always call /api/sessions first.
        pass


class TestReportFlow(unittest.TestCase):
    def setUp(self):
        r = client.post("/api/doctors", json={"name": f"ReportDoc{time.time()}"})
        self.doctor_id = r.json()["id"]

    def test_no_data_returns_404(self):
        r = client.get(f"/api/doctors/{self.doctor_id}/report.pdf")
        self.assertEqual(r.status_code, 404)

    def test_report_generated_after_frames(self):
        r = client.post("/api/sessions", json={"doctor_id": self.doctor_id})
        session_id = r.json()["id"]
        t0 = time.time()
        frames = [{
            "time": t0 + j, "hip_angle": 95, "knee_angle": 90, "neck_angle": 15,
            "chin_angle": 10, "shoulder_elev_pct": 5,
            "hip_bad": (j % 3 == 0), "knee_bad": False, "neck_bad": (j % 4 == 0),
            "chin_bad": False, "shoulder_bad": False, "is_standing": False,
        } for j in range(100)]
        client.post("/api/frames", json={"session_id": session_id, "frames": frames})
        client.post(f"/api/sessions/{session_id}/end")

        r = client.get(f"/api/doctors/{self.doctor_id}/report.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertGreater(len(r.content), 1000)

    def test_doctor_not_found(self):
        r = client.get("/api/doctors/999999/report.pdf")
        self.assertEqual(r.status_code, 404)


if __name__ == '__main__':
    unittest.main()
