// DentalPose Web — Main App
import { PoseLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
import { MODEL_URL, WASM_URL, Timing } from './config.js';
import { PostureTracker } from './tracking.js';
import { api } from './api.js';

const $ = (sel) => document.querySelector(sel);

const els = {
  nameScreen: $('#name-screen'), nameInput: $('#doctor-name-input'), nameSubmit: $('#doctor-name-submit'),
  calibScreen: $('#calib-screen'), calibBar: $('#calib-bar'), calibText: $('#calib-text'),
  monitorScreen: $('#monitor-screen'), video: $('#video'), overlay: $('#overlay'),
  statusLbl: $('#status-lbl'), startBtn: $('#start-btn'), recalibBtn: $('#recalib-btn'),
  reportBtn: $('#report-btn'), doctorLbl: $('#doctor-lbl'),
  metricHip: $('#metric-hip'), metricKnee: $('#metric-knee'), metricNeck: $('#metric-neck'),
  metricChin: $('#metric-chin'), metricShoulder: $('#metric-shoulder'),
  staleNotice: $('#stale-notice'), errorBanner: $('#error-banner'),
};

let doctor = null;
let tracker = new PostureTracker();
let landmarker = null;
let stream = null;
let sessionId = null;
let running = false;
let calibrating = false;
let calibFrames = [];
let calibStart = 0;
let frameBuffer = [];
let lastBatchSent = 0;
let ctx = els.overlay.getContext('2d');

function showScreen(name) {
  for (const s of [els.nameScreen, els.calibScreen, els.monitorScreen]) s.classList.add('hidden');
  ({ name: els.nameScreen, calib: els.calibScreen, monitor: els.monitorScreen })[name].classList.remove('hidden');
}

function showError(msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove('hidden');
  setTimeout(() => els.errorBanner.classList.add('hidden'), 6000);
}

// ---------------------------------------------------------
// شروع: اسم دکتر
// ---------------------------------------------------------
els.nameSubmit.addEventListener('click', onSubmitName);
els.nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') onSubmitName(); });

async function onSubmitName() {
  const name = els.nameInput.value.trim();
  if (!name) return;
  try {
    doctor = await api.createOrGetDoctor(name);
    els.doctorLbl.textContent = doctor.display_name;
    document.title = `DentalPose — ${doctor.display_name}`;

    if (doctor.has_baseline) {
      const baseline = await api.getBaseline(doctor.id);
      tracker.importBaseline(baseline);
      const age = tracker.baselineAgeDays();
      if (age != null && age > 30) {
        els.staleNotice.textContent = `Calibration is about ${Math.round(age)} days old — consider recalibrating.`;
        els.staleNotice.classList.remove('hidden');
      }
    }
    await initCamera();
    await initModel();
    showScreen('monitor');
    requestAnimationFrame(loop);
  } catch (e) {
    showError(`Could not start: ${e.message}`);
  }
}

// ---------------------------------------------------------
// دوربین + مدل
// ---------------------------------------------------------
async function initCamera() {
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  });
  els.video.srcObject = stream;
  await els.video.play();
  els.overlay.width = els.video.videoWidth || 1280;
  els.overlay.height = els.video.videoHeight || 720;
}

async function initModel() {
  const vision = await FilesetResolver.forVisionTasks(WASM_URL);
  landmarker = await PoseLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
    runningMode: 'VIDEO',
    numPoses: 1,
    outputSegmentationMasks: false,
  });
}

// ---------------------------------------------------------
// حلقه‌ی اصلی
// ---------------------------------------------------------
function loop() {
  if (landmarker && els.video.readyState >= 2) {
    const result = landmarker.detectForVideo(els.video, performance.now());
    processResult(result);
  }
  requestAnimationFrame(loop);
}

function processResult(result) {
  const w = els.overlay.width, h = els.overlay.height;
  ctx.clearRect(0, 0, w, h);

  if (!result.landmarks || !result.landmarks.length) return;
  const lm = result.landmarks[0];
  const lmWorld = result.worldLandmarks ? result.worldLandmarks[0] : null;

  drawSkeleton(lm, w, h);

  if (calibrating) {
    const raw = tracker.rawAnglesForCalibration(lm, lmWorld, w, h);
    if (raw) calibFrames.push(raw);
    const elapsed = (Date.now() - calibStart) / 1000;
    const pct = Math.min(elapsed / Timing.CALIBRATION_SEC, 1);
    els.calibBar.style.width = `${pct * 100}%`;
    els.calibText.textContent = `Hold still... ${Math.max(0, Timing.CALIBRATION_SEC - elapsed).toFixed(0)}s`;
    if (elapsed >= Timing.CALIBRATION_SEC) finishCalibration();
    return;
  }

  if (!running || !tracker.baseline) return;
  const pf = tracker.processLandmarks(lm, lmWorld, w, h);
  if (!pf) return;
  updateMetricsUI(pf);
  bufferFrame(pf);
}

function drawSkeleton(lm, w, h) {
  const pairs = [[11,12],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28],[11,13],[12,14]];
  ctx.strokeStyle = '#00D4AA'; ctx.lineWidth = 2;
  for (const [a, b] of pairs) {
    if (!lm[a] || !lm[b]) continue;
    ctx.beginPath();
    ctx.moveTo(lm[a].x * w, lm[a].y * h);
    ctx.lineTo(lm[b].x * w, lm[b].y * h);
    ctx.stroke();
  }
}

// ---------------------------------------------------------
// کالیبراسیون
// ---------------------------------------------------------
function startCalibration() {
  calibrating = true;
  calibFrames = [];
  calibStart = Date.now();
  showScreen('calib');
}

async function finishCalibration() {
  calibrating = false;
  tracker.setBaselineFromRawFrames(calibFrames);
  const { ok, msg } = tracker.validateBaseline();
  if (!ok) showError(`Calibration warning: ${msg}`);
  try {
    await api.saveBaseline(doctor.id, tracker.exportBaseline());
  } catch (e) {
    showError(`Could not save baseline to server: ${e.message}`);
  }
  showScreen('monitor');
  await actuallyStartSession();
}

// ---------------------------------------------------------
// سشن
// ---------------------------------------------------------
els.startBtn.addEventListener('click', onToggleSession);
els.recalibBtn.addEventListener('click', () => {
  if (running) { showError('Stop the session before recalibrating.'); return; }
  tracker.clearBaseline();
  startCalibration();
});
els.reportBtn.addEventListener('click', () => {
  if (doctor) window.open(api.reportUrl(doctor.id), '_blank');
});

async function onToggleSession() {
  if (running) {
    running = false;
    await flushFrames();
    if (sessionId) await api.endSession(sessionId).catch(() => {});
    els.startBtn.textContent = '▶  Start Session';
    els.statusLbl.textContent = 'Session ended';
    return;
  }
  if (!tracker.baseline) { startCalibration(); return; }
  await actuallyStartSession();
}

async function actuallyStartSession() {
  try {
    const s = await api.startSession(doctor.id);
    sessionId = s.id;
  } catch (e) {
    showError(`Could not start session on server: ${e.message}`);
    return;
  }
  tracker.reset();
  frameBuffer = [];
  lastBatchSent = Date.now();
  running = true;
  els.startBtn.textContent = '■  Stop Session';
  els.statusLbl.textContent = 'Tracking...';
}

function updateMetricsUI(pf) {
  els.metricHip.textContent = `${pf.hipAngle.toFixed(1)}°`;
  els.metricKnee.textContent = `${pf.kneeAngle.toFixed(1)}°`;
  els.metricNeck.textContent = `${pf.neckAngle.toFixed(1)}°`;
  els.metricChin.textContent = `${pf.chinAngle.toFixed(1)}°`;
  els.metricShoulder.textContent = `+${pf.shoulderElevPct.toFixed(1)}%`;

  for (const [el, bad, skip] of [
    [els.metricHip, pf.hipBad, pf.isStanding], [els.metricKnee, pf.kneeBad, pf.isStanding],
    [els.metricNeck, pf.neckBad, false], [els.metricChin, pf.chinBad, false],
    [els.metricShoulder, pf.shoulderBad, false],
  ]) {
    el.className = skip ? 'metric-dim' : (bad ? 'metric-bad' : 'metric-good');
  }

  if (pf.isStanding) {
    els.statusLbl.textContent = pf.anyBad ? '⚠ Bad Posture (standing)' : '🧍 Standing';
    els.statusLbl.className = pf.anyBad ? 'status-bad' : 'status-dim';
  } else {
    els.statusLbl.textContent = pf.anyBad ? '⚠ Bad Posture' : '✓ Good';
    els.statusLbl.className = pf.anyBad ? 'status-bad' : 'status-good';
  }
}

// ---------------------------------------------------------
// batching فریم‌ها به سرور — هر چند ثانیه یه‌بار، نه هر فریم
// ---------------------------------------------------------
function bufferFrame(pf) {
  frameBuffer.push({
    time: Date.now() / 1000,
    hip_angle: pf.hipAngle, knee_angle: pf.kneeAngle, neck_angle: pf.neckAngle,
    chin_angle: pf.chinAngle, shoulder_elev_pct: pf.shoulderElevPct,
    hip_bad: pf.hipBad, knee_bad: pf.kneeBad, neck_bad: pf.neckBad,
    chin_bad: pf.chinBad, shoulder_bad: pf.shoulderBad, is_standing: pf.isStanding,
  });
  if (Date.now() - lastBatchSent > Timing.FRAME_BATCH_SEC * 1000) flushFrames();
}

async function flushFrames() {
  if (!frameBuffer.length || !sessionId) return;
  const batch = frameBuffer;
  frameBuffer = [];
  lastBatchSent = Date.now();
  try {
    await api.sendFrames(sessionId, batch);
  } catch (e) {
    console.warn('Failed to send frame batch, re-queueing', e);
    frameBuffer = batch.concat(frameBuffer);  // بعداً دوباره امتحان می‌کنه
  }
}

setInterval(() => { if (running) flushFrames(); }, Timing.FRAME_BATCH_SEC * 1000);

// قبل از بستن صفحه، آخرین فریم‌ها رو ارسال کن (best effort)
window.addEventListener('beforeunload', () => {
  if (frameBuffer.length && sessionId) {
    navigator.sendBeacon(
      `${api.reportUrl(doctor?.id).split('/api/')[0]}/api/frames`,
      new Blob([JSON.stringify({ session_id: sessionId, frames: frameBuffer })], { type: 'application/json' })
    );
  }
});
