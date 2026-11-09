<script setup>
import { onMounted, ref } from 'vue'
import { store, api } from './store'
import UploadView from './views/UploadView.vue'
import ReviewView from './views/ReviewView.vue'
import ExportView from './views/ExportView.vue'

const steps = ['Unggah', 'Tinjau', 'Ekspor']
const error = ref('')

onMounted(async () => {
  try {
    store.defaults = await api('/defaults')
    store.params = { ...store.defaults }
  } catch {
    error.value = 'Server tidak bisa dihubungi. Jalankan backend dulu: python main.py'
  }
})
</script>

<template>
  <header class="topbar">
    <div class="brand"><span class="logo">✂</span> <span class="brand-name">JedaCut</span></div>
    <nav class="steps">
      <button v-for="(name, i) in steps" :key="name" class="pill"
              :class="{ active: store.step === i + 1, done: store.step > i + 1 }"
              :disabled="store.step <= i + 1" @click="store.step = i + 1">
        {{ store.step > i + 1 ? '✓' : i + 1 }} {{ name }}
      </button>
    </nav>
  </header>

  <main>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="store.params">
      <UploadView v-if="store.step === 1" />
      <ReviewView v-else-if="store.step === 2" />
      <ExportView v-else />
    </template>
  </main>
</template>

<style>
/* Tema gelap ala aplikasi editor video (rancangan high-fidelity 3.3.3) */
:root {
  --bg: #111318; --panel: #1a1d24; --panel2: #232731; --border: #2e3340;
  --text: #e6e8ec; --muted: #8b93a1; --accent: #4f8cff; --cut: #e5484d; --ok: #3dd68c;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-size: 30px; margin: 0 0 4px; }
h3 { margin: 0 0 14px; font-size: 17px; }
.muted { color: var(--muted); }
.error { color: var(--cut); }

.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px;
  border-bottom: 1px solid var(--border); background: var(--panel); }
.brand { font-weight: 700; font-size: 20px; display: flex; gap: 10px; align-items: center; }
.logo { width: 34px; height: 34px; border-radius: 8px; background: var(--accent); display: grid; place-items: center; }
.steps { display: flex; gap: 8px; }
.pill { border-radius: 99px; padding: 6px 16px; white-space: nowrap; }
.pill.active { background: var(--accent); border-color: var(--accent); color: #fff; opacity: 1; }
.pill.done { color: var(--ok); }

.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 24px; align-items: start; }
/* flex-wrap: isi baris turun ke bawah saat layar sempit, bukan melebar keluar layar */
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.spacer { flex: 1; }

button, .btn { background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 8px;
  padding: 9px 16px; font: inherit; cursor: pointer; text-decoration: none; display: inline-block; text-align: center; }
button:hover:not(:disabled), .btn:hover { border-color: var(--accent); }
button:disabled { opacity: .45; cursor: default; }
.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
.block { width: 100%; padding: 13px; }

input, select { background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 10px; font: inherit; width: 100%; }
input[type=checkbox] { width: auto; }
input[type=range] { padding: 0; accent-color: var(--accent); }
label { font-size: 13px; color: var(--muted); }

.bar { height: 10px; border-radius: 99px; background: var(--panel2); overflow: hidden; }
.bar > div { height: 100%; background: var(--accent); transition: width .3s; }
video { width: 100%; background: #000; border-radius: 10px; display: block; }

/* minmax(0, 1fr), bukan 1fr: teks panjang (nama file) tidak boleh memaksa kolom lebih lebar dari layar */
@media (max-width: 900px) { .grid { grid-template-columns: minmax(0, 1fr); } }

/* Ukuran HP */
@media (max-width: 640px) {
  main { padding: 20px 16px 48px; }
  h1 { font-size: 24px; }
  .card { padding: 14px; }
  .topbar { padding: 10px 16px; }
  .brand-name { display: none; }
  .pill { padding: 5px 10px; font-size: 13px; }
}
</style>
