<script setup>
import { ref } from 'vue'
import { store, analyze, startRender, fmtTime, fmtSize } from '../store'
import TrimSettings from '../components/TrimSettings.vue'

const input = ref(null)
const progress = ref(0)
const dragging = ref(false)
const busy = ref(false)
const error = ref('')

function upload(file) {
  if (!file) return
  URL.revokeObjectURL(store.fileUrl)
  Object.assign(store, { file, fileUrl: URL.createObjectURL(file), info: null, edl: null })
  error.value = ''
  progress.value = 0

  // Pakai XMLHttpRequest karena fetch belum menyediakan event progres unggah.
  const xhr = new XMLHttpRequest()
  const form = new FormData()
  form.append('file', file)
  xhr.upload.onprogress = (e) => (progress.value = Math.round((e.loaded / e.total) * 100))
  xhr.onload = () => {
    let data = {}
    try { data = JSON.parse(xhr.responseText) } catch { /* balasan bukan JSON */ }
    if (xhr.status === 200) store.info = data
    else error.value = data.detail || 'Unggah gagal'
  }
  xhr.onerror = () => (error.value = 'Koneksi ke server gagal')
  xhr.open('POST', '/api/upload')
  xhr.send(form)
}

function onDrop(e) {
  dragging.value = false
  upload(e.dataTransfer.files[0])
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
             @dragleave="dragging = false" @drop.prevent="onDrop">
        <input ref="input" type="file" hidden accept=".mp4,.mkv,.mov,.webm,.wav,.mp3"
               @change="upload($event.target.files[0])" />
        <div class="drop-icon">⇪</div>
        <strong>Tarik &amp; lepas video di sini</strong>
        <span>atau <u>pilih file</u></span>
        <small>MP4 · MKV · MOV · WEBM · WAV / MP3</small>
      </label>

      <div v-if="store.file" class="card file">
        <video class="thumb" :src="store.fileUrl" muted preload="metadata"></video>
        <div class="file-info">
          <strong>{{ store.file.name }}</strong>
          <div v-if="!store.info && !error" class="bar"><div :style="{ width: progress + '%' }"></div></div>
          <span v-if="store.info" class="ok">
            ✓ Audio terdeteksi · {{ fmtTime(store.info.duration) }} · {{ fmtSize(store.info.size) }}
          </span>
          <span v-else-if="!error" class="muted">Mengunggah {{ progress }}%</span>
        </div>
        <button @click="input.click()">Ganti file</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <TrimSettings :disabled="!store.info || busy" :busy="busy" @analyze="run(false)" @render="run(true)" />
  </div>
</template>

<style scoped>
.drop { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 56px 20px;
  border: 2px dashed var(--border); border-radius: 12px; cursor: pointer; color: var(--text); font-size: 15px; }
.drop.dragging, .drop:hover { border-color: var(--accent); background: var(--panel); }
.drop strong { font-size: 20px; }
.drop small { color: var(--muted); }
.drop-icon { font-size: 36px; color: var(--accent); }
.file { display: flex; gap: 16px; align-items: center; margin-top: 16px; }
.thumb { width: 150px; height: 84px; object-fit: cover; }
.file-info { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.file-info strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ok { color: var(--ok); font-size: 14px; }
</style>
