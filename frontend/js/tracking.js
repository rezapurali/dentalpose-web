// DentalPose Web — Tracking Engine
// پورت مستقیم tracking.py؛ فرمول‌ها دقیقاً همونن تا با نسخه‌ی دسکتاپ یکسان باشه.

import { LandmarkIdx, PostureThresholds, Timing } from './config.js';

function calculateAngle2D(a, b, c) {
  const radians = Math.atan2(c[1] - b[1], c[0] - b[0]) - Math.atan2(a[1] - b[1], a[0] - b[0]);
  let angle = Math.abs(radians * 180 / Math.PI);
  return angle > 180 ? 360 - angle : angle;
}

function calculateAngle3D(a, b, c) {
  const v1 = [a[0]-b[0], a[1]-b[1], a[2]-b[2]];
  const v2 = [c[0]-b[0], c[1]-b[1], c[2]-b[2]];
  const n1 = Math.hypot(...v1), n2 = Math.hypot(...v2);
  if (n1 < 1e-6 || n2 < 1e-6) return 0;
  const dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2];
  const cosA = Math.max(-1, Math.min(1, dot / (n1 * n2)));
  return Math.acos(cosA) * 180 / Math.PI;
}

function weightedMid(pL, pR, visL, visR) {
  const sum = visL + visR;
  const wL = sum < 1e-3 ? 0.5 : visL / sum;
  const wR = sum < 1e-3 ? 0.5 : visR / sum;
  return pL.map((v, i) => v * wL + pR[i] * wR);
}

function getPt(lm, idx, w, h) {
  return [lm[idx].x * w, lm[idx].y * h];
}
function getPtWorld(lmWorld, idx) {
  const p = lmWorld[idx];
  return [p.x, p.y, p.z];
}
function getVis(lm, idx) {
  return lm[idx].visibility ?? 1.0;
}

class RollingMean {
  constructor(maxLen) { this.maxLen = maxLen; this.buf = []; }
  push(v) { this.buf.push(v); if (this.buf.length > this.maxLen) this.buf.shift(); }
  mean() { return this.buf.reduce((a, b) => a + b, 0) / (this.buf.length || 1); }
  clear() { this.buf = []; }
}

export class PostureFrame {
  constructor(fields) { Object.assign(this, fields); }
  get anyBad() {
    return this.hipBad || this.kneeBad || this.neckBad || this.chinBad || this.shoulderBad;
  }
}

export class PostureTracker {
  constructor() {
    this._hipHist = new RollingMean(Timing.SMOOTH_WINDOW);
    this._kneeHist = new RollingMean(Timing.SMOOTH_WINDOW);
    this._neckHist = new RollingMean(Timing.SMOOTH_WINDOW);
    this._chinHist = new RollingMean(Timing.SMOOTH_WINDOW);
    this._shHist = new RollingMean(Timing.SMOOTH_WINDOW);

    this.baseline = null;           // {hip, knee, neck, chin}
    this.shoulderBaseline = null;
    this.calibratedAt = null;

    this._standFrames = 0;
    this._sitFrames = 0;
    this.isStanding = false;
  }

  reset() {
    [this._hipHist, this._kneeHist, this._neckHist, this._chinHist, this._shHist].forEach(h => h.clear());
    this._standFrames = 0;
    this._sitFrames = 0;
    this.isStanding = false;
  }

  clearBaseline() {
    this.baseline = null;
    this.shoulderBaseline = null;
  }

  exportBaseline() {
    if (!this.baseline || this.shoulderBaseline == null) return null;
    return {
      hip: this.baseline.hip, knee: this.baseline.knee,
      neck: this.baseline.neck, chin: this.baseline.chin,
      shoulder_baseline: this.shoulderBaseline,
    };
  }

  importBaseline(data) {
    if (!data) return false;
    const required = ['hip', 'knee', 'neck', 'chin'];
    if (!required.every(k => k in data)) return false;
    this.baseline = { hip: data.hip, knee: data.knee, neck: data.neck, chin: data.chin };
    this.shoulderBaseline = data.shoulder_baseline;
    this.calibratedAt = data.calibrated_at ? data.calibrated_at * 1000 : Date.now();
    return true;
  }

  baselineAgeDays() {
    if (!this.calibratedAt) return null;
    return (Date.now() - this.calibratedAt) / 86400000;
  }

  /** میانگین چند فریم خام (حین کالیبراسیون) رو به baseline تبدیل می‌کنه */
  setBaselineFromRawFrames(rawFrames) {
    if (!rawFrames.length) return;
    const avg = (key) => rawFrames.reduce((s, r) => s + r[key], 0) / rawFrames.length;
    this.baseline = { hip: avg('hip'), knee: avg('knee'), neck: avg('neck'), chin: avg('chin') };
    this.shoulderBaseline = avg('sh_norm');
    this.calibratedAt = Date.now();
  }

  validateBaseline() {
    if (!this.baseline) return { ok: false, msg: 'Baseline not set' };
    const { hip, neck } = this.baseline;
    if (!(hip >= 50 && hip <= 140)) return { ok: false, msg: `Hip baseline (${hip.toFixed(0)}°) out of expected range — please recalibrate` };
    if (!(neck >= 0 && neck <= 60)) return { ok: false, msg: `Neck baseline (${neck.toFixed(0)}°) unusual — please recalibrate` };
    return { ok: true, msg: 'OK' };
  }

  /**
   * زوایای خام یه فریم رو حساب می‌کنه — هم برای کالیبراسیون هم اجرای واقعی
   * استفاده میشه (دقیقاً مثل tracking.py که همین هماهنگی رو رعایت می‌کرد)
   */
  _computeRawAngles(lm, lmWorld, w, h) {
    const idx = LandmarkIdx;
    const nose = getPt(lm, idx.NOSE, w, h);
    const mouthL = getPt(lm, idx.MOUTH_LEFT, w, h), mouthR = getPt(lm, idx.MOUTH_RIGHT, w, h);
    const shoulderL = getPt(lm, idx.SHOULDER_L, w, h), shoulderR = getPt(lm, idx.SHOULDER_R, w, h);
    const hipL = getPt(lm, idx.HIP_L, w, h), hipR = getPt(lm, idx.HIP_R, w, h);
    const kneeL = getPt(lm, idx.KNEE_L, w, h), kneeR = getPt(lm, idx.KNEE_R, w, h);
    const ankleL = getPt(lm, idx.ANKLE_L, w, h), ankleR = getPt(lm, idx.ANKLE_R, w, h);
    const earL = getPt(lm, idx.EAR_L, w, h), earR = getPt(lm, idx.EAR_R, w, h);

    const visShL = getVis(lm, idx.SHOULDER_L), visShR = getVis(lm, idx.SHOULDER_R);
    const visHipL = getVis(lm, idx.HIP_L), visHipR = getVis(lm, idx.HIP_R);
    const visKneeL = getVis(lm, idx.KNEE_L), visKneeR = getVis(lm, idx.KNEE_R);
    const visAnkleL = getVis(lm, idx.ANKLE_L), visAnkleR = getVis(lm, idx.ANKLE_R);
    const visMouthL = getVis(lm, idx.MOUTH_LEFT), visMouthR = getVis(lm, idx.MOUTH_RIGHT);
    const visEarL = getVis(lm, idx.EAR_L), visEarR = getVis(lm, idx.EAR_R);

    const shMid = weightedMid(shoulderL, shoulderR, visShL, visShR);
    const hipMid = weightedMid(hipL, hipR, visHipL, visHipR);
    const kneeMid = weightedMid(kneeL, kneeR, visKneeL, visKneeR);
    const moMid = weightedMid(mouthL, mouthR, visMouthL, visMouthR);
    const shWidth = Math.abs(shoulderL[0] - shoulderR[0]) + 1e-6;

    // هیپ: از world landmarks (متر واقعی)، همون فیکس حساسیت به خم‌شدن جلو
    let hipAngle;
    if (lmWorld) {
      const shMidW = weightedMid(getPtWorld(lmWorld, idx.SHOULDER_L), getPtWorld(lmWorld, idx.SHOULDER_R), visShL, visShR);
      const hipMidW = weightedMid(getPtWorld(lmWorld, idx.HIP_L), getPtWorld(lmWorld, idx.HIP_R), visHipL, visHipR);
      const kneeMidW = weightedMid(getPtWorld(lmWorld, idx.KNEE_L), getPtWorld(lmWorld, idx.KNEE_R), visKneeL, visKneeR);
      hipAngle = calculateAngle3D(shMidW, hipMidW, kneeMidW);
    } else {
      hipAngle = calculateAngle2D(shMid, hipMid, kneeMid);
    }

    // زانو: هر دو پا جدا (۲بعدی) + وزن‌دار بر اساس visibility — مقاوم به چرخش بدن
    const kneeAngleL = calculateAngle2D(hipL, kneeL, ankleL);
    const kneeAngleR = calculateAngle2D(hipR, kneeR, ankleR);
    const visL = (visHipL + visKneeL + visAnkleL) / 3;
    const visR = (visHipR + visKneeR + visAnkleR) / 3;
    const visSum = visL + visR;
    const kneeAngle = visSum < 1e-3 ? (kneeAngleL + kneeAngleR) / 2
                                     : (kneeAngleL * visL + kneeAngleR * visR) / visSum;

    const dx = nose[0] - shMid[0], dy = shMid[1] - nose[1];
    const neckAngle = Math.abs(Math.atan2(dx, dy) * 180 / Math.PI);

    const shVec = [shoulderR[0]-shoulderL[0], shoulderR[1]-shoulderL[1]];
    let perp = [-shVec[1], shVec[0]];
    if (perp[1] < 0) perp = [-perp[0], -perp[1]];
    const chinVec = [moMid[0]-shMid[0], moMid[1]-shMid[1]];
    const upPerp = [-perp[0], -perp[1]];
    const chinDot = chinVec[0]*upPerp[0] + chinVec[1]*upPerp[1];
    const chinCos = Math.max(-1, Math.min(1, chinDot / (Math.hypot(...chinVec) * Math.hypot(...upPerp) + 1e-6)));
    const chinAngle = Math.acos(chinCos) * 180 / Math.PI;

    // شونه: دو طرف، وزن‌دار
    const shEarDistL = Math.hypot(earL[0]-shoulderL[0], earL[1]-shoulderL[1]);
    const shEarDistR = Math.hypot(earR[0]-shoulderR[0], earR[1]-shoulderR[1]);
    const visEsL = (visEarL + visShL) / 2, visEsR = (visEarR + visShR) / 2;
    const visEsSum = visEsL + visEsR;
    const shEarDist = visEsSum < 1e-3 ? (shEarDistL + shEarDistR) / 2
                                       : (shEarDistL * visEsL + shEarDistR * visEsR) / visEsSum;
    const shNorm = shEarDist / shWidth;

    return { hip: hipAngle, knee: kneeAngle, neck: neckAngle, chin: chinAngle, sh_norm: shNorm };
  }

  /** برای کالیبراسیون — فقط زوایای خام، بدون baseline لازم */
  rawAnglesForCalibration(lm, lmWorld, w, h) {
    try { return this._computeRawAngles(lm, lmWorld, w, h); }
    catch (e) { console.warn('rawAnglesForCalibration failed', e); return null; }
  }

  /** پردازش کامل یه فریم — نیاز به baseline داره */
  processLandmarks(lm, lmWorld, w, h) {
    if (!this.baseline) return null;
    try {
      const raw = this._computeRawAngles(lm, lmWorld, w, h);
      this._hipHist.push(raw.hip);
      this._kneeHist.push(raw.knee);
      this._neckHist.push(raw.neck);
      this._chinHist.push(raw.chin);
      this._shHist.push(raw.sh_norm);

      const sHip = this._hipHist.mean();
      const sKnee = this._kneeHist.mean();
      const sNeck = this._neckHist.mean();
      const sChin = this._chinHist.mean();
      const shElev = Math.max(0, (this._shHist.mean() - this.shoulderBaseline) / this.shoulderBaseline * 100);

      const thr = PostureThresholds;
      const looksStanding = sHip > thr.STANDING_HIP_MIN && sKnee > thr.STANDING_KNEE_MIN;
      if (looksStanding) { this._standFrames++; this._sitFrames = 0; }
      else { this._sitFrames++; this._standFrames = 0; }

      if (!this.isStanding && this._standFrames >= Timing.STAND_HOLD_FRAMES) this.isStanding = true;
      else if (this.isStanding && this._sitFrames >= Timing.SIT_HOLD_FRAMES) this.isStanding = false;

      const hipBad = !this.isStanding && !(thr.HIP_MIN <= sHip && sHip <= thr.HIP_MAX);
      const kneeBad = !this.isStanding && !(thr.KNEE_MIN <= sKnee && sKnee <= thr.KNEE_MAX);
      const neckBad = sNeck > thr.NECK_MAX;
      const chinBad = sChin > thr.CHIN_MAX;
      const shBad = shElev > thr.SHOULDER_ELEV_MAX;

      return new PostureFrame({
        hipAngle: sHip, kneeAngle: sKnee, neckAngle: sNeck, chinAngle: sChin,
        shoulderElevPct: shElev, hipBad, kneeBad, neckBad, chinBad, shoulderBad: shBad,
        isStanding: this.isStanding,
      });
    } catch (e) {
      console.warn('processLandmarks failed', e);
      return null;
    }
  }
}
