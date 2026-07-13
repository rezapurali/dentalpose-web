// DentalPose Web — API Client
import { API_BASE } from './config.js';

async function req(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const err = new Error(detail.detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res;
}

export const api = {
  async createOrGetDoctor(name) {
    const res = await req('/api/doctors', { method: 'POST', body: JSON.stringify({ name }) });
    return res.json();
  },

  async getBaseline(doctorId) {
    try {
      const res = await req(`/api/doctors/${doctorId}/baseline`);
      return res.json();
    } catch (e) {
      if (e.status === 404) return null;
      throw e;
    }
  },

  async saveBaseline(doctorId, baseline) {
    const res = await req(`/api/doctors/${doctorId}/baseline`, {
      method: 'POST', body: JSON.stringify(baseline),
    });
    return res.json();
  },

  async startSession(doctorId) {
    const res = await req('/api/sessions', { method: 'POST', body: JSON.stringify({ doctor_id: doctorId }) });
    return res.json();
  },

  async endSession(sessionId) {
    await req(`/api/sessions/${sessionId}/end`, { method: 'POST' });
  },

  async sendFrames(sessionId, frames) {
    if (!frames.length) return;
    await req('/api/frames', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, frames }),
    });
  },

  reportUrl(doctorId) {
    return `${API_BASE}/api/doctors/${doctorId}/report.pdf`;
  },
};
