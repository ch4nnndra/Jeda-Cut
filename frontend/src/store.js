import { reactive } from 'vue'

// State bersama ketiga layar. Satu objek reactive sudah cukup sebagai pengganti Pinia + Router.
export const store = reactive({
  step: 1,          // 1 Unggah, 2 Periksa, 3 Ekspor
  defaults: null,   // preset Default dari server (Tabel 3.2)
  params: null,     // pengaturan trim yang sedang dipakai
  file: null,       // File asli di browser
  fileUrl: '',      // object URL untuk preview tanpa perlu endpoint tambahan
  info: null,       // balasan /api/upload: id, durasi, has_video, dll
  edl: null,
  timeline: null,
  autoActions: '', // aksi hasil analisis, untuk mendeteksi perubahan manual di Daftar Potongan
})

// Alamat backend. Kosong = domain yang sama (dev lewat proxy Vite, atau dilayani FastAPI).
// Saat frontend di Vercel dan backend di host lain, isi VITE_API_URL (contoh: https://xxxx.trycloudflare.com).
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
  store.autoActions = actionsOf(r.edl)
}

export const actionsOf = (edl) => edl.segments.map((s) => s.action).join()

// Simpan EDL terakhir (hasil edit di layar Periksa) lalu mulai render.
export async function startRender() {
  await api(`/edl/${store.info.id}`, 'PUT', store.edl)
  await api(`/render/${store.info.id}`, 'POST')
  store.step = 3
}

export function resetAll() {
  URL.revokeObjectURL(store.fileUrl)
  Object.assign(store, { step: 1, file: null, fileUrl: '', info: null, edl: null, timeline: null, autoActions: '' })
  Object.assign(store.params, store.defaults)
}

export function fmtTime(sec) {
  // Dibulatkan ke 0,1 s dulu agar 59,96 tidak tampil sebagai "0:60.0".
  const t = Math.round(sec * 10)
  return `${Math.floor(t / 600)}:${((t % 600) / 10).toFixed(1).padStart(4, '0')}`
}

// Durasi dalam bahasa sehari-hari: "45 menit 3 detik", "1 jam 5 menit", "16 detik".
export function fmtLong(sec) {
  const t = Math.round(sec)
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60
  if (h) return `${h} jam` + (m ? ` ${m} menit` : '')
  if (m) return `${m} menit` + (s ? ` ${s} detik` : '')
  return `${s} detik`
}

export const fmtSize = (bytes) => (bytes / 1048576).toFixed(1) + ' MB'
