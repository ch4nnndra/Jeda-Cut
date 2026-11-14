<script setup>
import { ref } from 'vue'
import { store, API, analyze, startRender, fmtTime, fmtSize } from '../store'
import TrimSettings from '../components/TrimSettings.vue'

const input = ref(null)
const progress = ref(0)
const dragging = ref(false)
const busy = ref(false)
const error = ref('')
const FORMATS = ['.mp4', '.mkv', '.mov', '.webm', '.wav', '.mp3']
let xhr = null // unggahan yang sedang berjalan

function upload(file) {
  if (!file) return
  // File yang ditarik ke area unggah tidak tersaring atribut accept, jadi formatnya dicek di sini
  // supaya file yang salah tidak sempat diunggah penuh dulu.
  if (!FORMATS.some((ext) => file.name.toLowerCase().endsWith(ext))) {
    error.value = 'Format file tidak didukung. Gunakan MP4, MKV, MOV, WEBM, WAV, atau MP3.'
    return
  }
  // Batalkan unggahan sebelumnya. Tanpa ini, balasan file lama yang datang belakangan
  // bisa menimpa info file baru, lalu yang dianalisis justru video yang salah.
  xhr?.abort()
  URL.revokeObjectURL(store.fileUrl)
  Object.assign(store, { file, fileUrl: URL.createObjectURL(file), info: null, edl: null })
  error.value = ''
  progress.value = 0

  // Pakai XMLHttpRequest karena fetch belum menyediakan event progres unggah.
  const req = (xhr = new XMLHttpRequest())
  const form = new FormData()
  form.append('file', file)
  req.upload.onprogress = (e) => (progress.value = Math.round((e.loaded / e.total) * 100))
  req.onload = () => {
    let data = {}
    try { data = JSON.parse(req.responseText) } catch { /* balasan bukan JSON, misal halaman error proxy */ }
    if (req.status === 200) store.info = data
    else if (req.status === 413) error.value = 'File terlalu besar untuk diunggah lewat koneksi ini. Coba video yang lebih kecil (di bawah 100 MB).'
    else error.value = data.detail || 'Unggahan gagal. Coba lagi beberapa saat lagi.'
  }
  req.onerror = () => (error.value = 'Unggahan terputus. Periksa koneksi internet, lalu coba lagi.')
  req.open('POST', `${API}/upload`)
  req.send(form)
}

async function run(withRender) {
  busy.value = true
  error.value = ''
  try {
    await analyze()
    if (withRender) await startRender()
    else store.step = 2
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1>Hapus jeda otomatis, tanpa edit manual</h1>
  <p class="muted">Unggah video, JedaCut menandai jeda dari audionya, Anda tinjau daftar potongannya, lalu render jadi MP4 yang lebih singkat.</p>

  <div class="grid" style="margin-top: 24px">
    <div>
      <label class="drop" :class="{ dragging }" @dragover.prevent="dragging = true"
             @dragleave="dragging = false"
             @drop.prevent="dragging = false; upload($event.dataTransfer.files[0])">
        <!-- sr-only, bukan hidden: input tetap bisa difokus Tab lalu dibuka dengan Enter/Space -->
        <input ref="input" type="file" class="sr-only" :accept="FORMATS.join()"
               @change="upload($event.target.files[0])" />
        <div class="drop-icon">⇪</div>
        <strong>Tarik &amp; lepas video di sini</strong>
        <span>atau <u>pilih file</u></span>
        <small>MP4 · MKV · MOV · WEBM · WAV / MP3</small>
      </label>

      <div v-if="store.file" class="card file">
        <video class="thumb" :src="store.fileUrl" muted preload="metadata" aria-hidden="true"></video>
        <div class="file-info">
          <strong>{{ store.file.name }}</strong>
          <div v-if="!store.info && !error" class="bar" role="progressbar" aria-label="Progres unggah"
               aria-valuemin="0" aria-valuemax="100" :aria-valuenow="progress">
            <div :style="{ width: progress + '%' }"></div>
          </div>
          <span v-if="store.info" class="ok">
            ✓ Audio terdeteksi · {{ fmtTime(store.info.duration) }} · {{ fmtSize(store.info.size) }}
          </span>
          <span v-else-if="!error" class="muted">Mengunggah {{ progress }}%</span>
        </div>
        <button @click="input.click()">Ganti file</button>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </div>

    <TrimSettings :disabled="!store.info || busy" :busy="busy" @analyze="run(false)" @render="run(true)" />
  </div>
</template>

<style scoped>
.drop { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 56px 20px;
  border: 2px dashed var(--border); border-radius: 12px; cursor: pointer; color: var(--text); font-size: 15px; }
.drop.dragging, .drop:hover, .drop:focus-within { border-color: var(--accent); background: var(--panel); }
.drop:focus-within { outline: 2px solid var(--accent); outline-offset: 2px; }
.drop strong { font-size: 20px; }
.drop small { color: var(--muted); }
.drop-icon { font-size: 36px; color: var(--accent); }
.file { display: flex; gap: 16px; align-items: center; margin-top: 16px; }
.thumb { width: 150px; height: 84px; object-fit: cover; }
.file-info { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.file-info strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ok { color: var(--ok); font-size: 14px; }

@media (max-width: 640px) {
  .drop { padding: 36px 16px; }
  .file { flex-wrap: wrap; gap: 12px; }
  .thumb { width: 96px; height: 54px; }
  .file button { width: 100%; }
}
</style>
