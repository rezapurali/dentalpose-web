// DentalPose Web — Config
// دقیقاً همون مقادیر config.py نسخه‌ی دسکتاپ، تا رفتار یکسان بمونه

// اگه فرانت‌اند از همون سروری که API رو می‌ده سرو بشه (که پیش‌فرض همینه)،
// نیازی به آدرس جدا نیست — خالی یعنی "همین دامنه"
export const API_BASE = window.DENTALPOSE_API_BASE || "";

export const LandmarkIdx = {
  NOSE: 0,
  MOUTH_LEFT: 9, MOUTH_RIGHT: 10,
  EAR_L: 7, EAR_R: 8,
  SHOULDER_L: 11, SHOULDER_R: 12,
  HIP_L: 23, HIP_R: 24,
  KNEE_L: 25, KNEE_R: 26,
  ANKLE_L: 27, ANKLE_R: 28,
};

export const PostureThresholds = {
  HIP_MIN: 80, HIP_MAX: 110,
  KNEE_MIN: 80, KNEE_MAX: 100,
  NECK_MAX: 40,
  CHIN_MAX: 40,
  SHOULDER_ELEV_MAX: 15,
  STANDING_HIP_MIN: 150,
  STANDING_KNEE_MIN: 150,
};

export const Timing = {
  CALIBRATION_SEC: 15,
  SMOOTH_WINDOW: 15,
  STAND_HOLD_FRAMES: 20,
  SIT_HOLD_FRAMES: 20,
  FRAME_BATCH_SEC: 2.0,   // هر چند ثانیه فریم‌ها رو batch کنه و بفرسته سرور
};

export const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task";

export const WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
