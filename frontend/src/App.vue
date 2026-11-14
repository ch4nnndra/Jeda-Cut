<script setup>
import { onMounted, ref } from 'vue'
import { store, api } from './store'
import UploadView from './views/UploadView.vue'
import ReviewView from './views/ReviewView.vue'
import ExportView from './views/ExportView.vue'

const steps = ['Unggah', 'Periksa', 'Ekspor']
const error = ref('')

async function connect() {
  error.value = ''
  try {
    store.defaults = await api('/defaults')
    store.params = { ...store.defaults }
  } catch {
    error.value = 'Server JedaCut belum aktif atau tidak bisa dihubungi. Pastikan server sudah berjalan, lalu coba lagi.'
  }
}
onMounted(connect)

// Peringatan bawaan browser sebelum refresh/tutup tab, agar hasil analisis dan perubahan tidak hilang.
window.addEventListener('beforeunload', (e) => {
  if (store.edl) {
    e.preventDefault()
    e.returnValue = '' // browser lama butuh returnValue untuk memunculkan dialog
  }
})
</script>

<template>
  <header class="topbar">
    <div class="brand"><span class="logo">✂</span> <span class="brand-name">JedaCut</span></div>
    <nav class="steps">
      <button v-for="(name, i) in steps" :key="name" class="pill"
              :class="{ active: store.step === i + 1, done: store.step > i + 1 }"
              :aria-current="store.step === i + 1 ? 'step' : undefined"
              :disabled="store.step <= i + 1" @click="store.step = i + 1">
        {{ store.step > i + 1 ? '✓' : i + 1 }} {{ name }}
      </button>
    </nav>
  </header>

  <main>
    <div v-if="error" class="card offline">
      <p class="error" role="alert">{{ error }}</p>
      <button class="primary" @click="connect">Coba lagi</button>
    </div>
    <template v-else-if="store.params">
      <UploadView v-if="store.step === 1" />
      <ReviewView v-else-if="store.step === 2" />
      <ExportView v-else />
    </template>
  </main>
</template>

<style>
/* Tema gelap ala aplikasi editor video (rancangan high-fidelity 3.3.3).
   Pasangan warna teks dan kontrol memenuhi kontras WCAG 2.1 AA: teks >= 4.5:1, garis kontrol >= 3:1. */
:root {
  --bg: #111318; --panel: #1a1d24; --panel2: #232731;
  --border: #2e3340;        /* garis kartu (dekoratif) */
  --line: #6b7386;          /* garis tepi kontrol: input, select, tombol */
  --text: #e6e8ec; --muted: #8b93a1;
  --accent: #4f8cff;        /* aksen grafik: batang energi, progres, fokus */
  --accent-strong: #2563eb; /* latar tombol utama, teks putih 5.2:1 */
  --cut: #e5484d;           /* isian wilayah potong */
  --cut-text: #f87171;      /* teks merah di atas panel, 6.1:1 */
  --ok: #3dd68c;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-size: 30px; margin: 0 0 4px; }
h3 { margin: 0 0 14px; font-size: 17px; }
.muted { color: var(--muted); }
.error { color: var(--cut-text); }
.offline { max-width: 560px; margin: 40px auto; text-align: center; }
/* Tersembunyi secara visual tapi tetap bisa difokus keyboard dan dibaca pembaca layar */
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px;
  border-bottom: 1px solid var(--border); background: var(--panel); }
.brand { font-weight: 700; font-size: 20px; display: flex; gap: 10px; align-items: center; }
.logo { width: 34px; height: 34px; border-radius: 8px; background: var(--accent); display: grid; place-items: center; }
.steps { display: flex; gap: 8px; }
.pill { border-radius: 99px; padding: 6px 16px; white-space: nowrap; }
.pill.active { background: var(--accent-strong); border-color: var(--accent-strong); color: #fff; opacity: 1; }
.pill.done { color: var(--ok); }

.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 24px; align-items: start; }
/* flex-wrap: isi baris turun ke bawah saat layar sempit, bukan melebar keluar layar */
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.spacer { flex: 1; }

button, .btn { background: var(--panel2); color: var(--text); border: 1px solid var(--line); border-radius: 8px;
  padding: 9px 16px; font: inherit; cursor: pointer; text-decoration: none; display: inline-block; text-align: center; }
button:hover:not(:disabled), .btn:hover { border-color: var(--accent); }
button:disabled { opacity: .45; cursor: not-allowed; }
.primary { background: var(--accent-strong); border-color: var(--accent-strong); color: #fff; font-weight: 600; }
.primary:hover:not(:disabled), .btn.primary:hover { background: #1d4ed8; border-color: #1d4ed8; }
.block { width: 100%; padding: 13px; }

input, select { background: var(--bg); color: var(--text); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 10px; font: inherit; font-size: 15px; width: 100%; }
input[type=checkbox] { width: auto; accent-color: var(--accent-strong); }
input[type=range] { padding: 0; border: 0; accent-color: var(--accent); }
label { font-size: 13px; color: var(--muted); }
/* Field form: label membungkus inputnya, jadi teks label terhubung ke kontrol untuk pembaca layar */
.field { display: flex; flex-direction: column; gap: 4px; }

.bar { height: 10px; border-radius: 99px; background: var(--panel2); overflow: hidden; }
.bar > div { height: 100%; background: var(--accent); transition: width .3s; }
/* Kotak video tetap 16:9 seperti monitor preview editor video. Video portrait (HP) diberi bingkai hitam
   lewat object-fit: contain, jadi tingginya tidak memanjang dan timeline tetap terlihat tanpa scroll. */
video { width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: #000; border-radius: 10px; display: block; }

/* minmax(0, 1fr), bukan 1fr: teks panjang (nama file) tidak boleh memaksa kolom lebih lebar dari layar */
@media (max-width: 900px) { .grid { grid-template-columns: minmax(0, 1fr); } }

/* Layar sentuh: target sentuh minimal 44 px (WCAG 2.5.5) */
@media (pointer: coarse) {
  button, .btn, select, input:not([type=checkbox]):not(.sr-only) { min-height: 44px; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}

/* Ukuran HP */
@media (max-width: 640px) {
  main { padding: 20px 16px 48px; }
  h1 { font-size: 24px; }
  .card { padding: 14px; }
  .topbar { padding: 10px 16px; }
  .brand-name { display: none; }
  .pill { padding: 5px 10px; font-size: 13px; }
  /* Di HP kotak 16:9 membuat video portrait terlalu kecil, jadi pakai rasio asli tapi tinggi
     maksimal 60% layar. svh = tinggi layar saat bilah alamat browser terlihat (vh sebagai cadangan). */
  video { aspect-ratio: auto; max-height: 60vh; max-height: 60svh; }
}
</style>
