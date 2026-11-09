import { reactive } from 'vue'

// State bersama ketiga layar. Satu objek reactive sudah cukup sebagai pengganti Pinia + Router.
export const store = reactive({
  step: 1,          // 1 Unggah, 2 Tinjau, 3 Ekspor
  defaults: null,   // preset Default dari server (Tabel 3.2)
  params: null,     // pengaturan trim yang sedang dipakai
  file: null,       // File asli di browser
  fileUrl: '',      // object URL untuk preview tanpa perlu endpoint tambahan
  info: null,       // balasan /api/upload: id, durasi, has_video, dll
  edl: null,
  timeline: null,
})

// Alamat backend. Kosong = domain yang sama (dev lewat proxy Vite, atau dilayani FastAPI).
// Saat frontend di Vercel dan backend di host lain, isi VITE_API_URL (contoh: https://nama-space.hf.space).
export const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') + '/api'

export async function api(path, method = 'GET', body) {
  const res = await fetch(API + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body && JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const d = data.detail
    throw new Error(typeof d === 'string' ? d : d ? 'Pengaturan tidak valid' : res.statusText)
  }
  return data
}

export async function analyze() {
  const r = await api(`/analyze/${store.info.id}`, 'POST', store.params)
  store.edl = r.edl
  store.timeline = r.timeline
}

// Simpan EDL terakhir (hasil edit di layar Tinjau) lalu mulai render.
export async function startRender() {
  await api(`/edl/${store.info.id}`, 'PUT', store.edl)
  await api(`/render/${store.info.id}`, 'POST')
  store.step = 3
}

export function resetAll() {
  URL.revokeObjectURL(store.fileUrl)
  Object.assign(store, { step: 1, file: null, fileUrl: '', info: null, edl: null, timeline: null })
  Object.assign(store.params, store.defaults)
}

export const keptDuration = (segments) =>
  segments.reduce((t, s) => t + (s.action === 'keep' ? s.end - s.start : 0), 0)

export function fmtTime(sec) {
  // Dibulatkan ke 0,1 s dulu agar 59,96 tidak tampil sebagai "0:60.0".
  const t = Math.round(sec * 10)
  return `${Math.floor(t / 600)}:${((t % 600) / 10).toFixed(1).padStart(4, '0')}`
}

export const fmtSize = (bytes) => (bytes / 1048576).toFixed(1) + ' MB'

export const baseName = (name) => name.replace(/\.[^.]+$/, '')
