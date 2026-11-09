<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { store, analyze, startRender, keptDuration, fmtTime, baseName } from '../store'
import EdlTable from '../components/EdlTable.vue'
import AudioTimeline from '../components/AudioTimeline.vue'

const video = ref(null)
const mode = ref('result')   // 'result' = lompati segmen cut, 'original' = putar apa adanya
const now = ref(0)
const busy = ref(false)
const error = ref('')

const duration = store.info.duration
const cuts = computed(() => store.edl.segments.filter((s) => s.action === 'cut'))
const kept = computed(() => keptDuration(store.edl.segments))

// Preview "Hasil" tanpa render: saat playhead masuk segmen cut, langsung lompat ke akhir segmen.
// Dicek tiap frame layar (requestAnimationFrame) karena event timeupdate hanya ~4 kali per detik,
// sehingga potongan pendek bisa terlewat terdengar.
let raf = requestAnimationFrame(function tick() {
  const v = video.value
  if (v) {
    now.value = v.currentTime
    if (mode.value === 'result' && !v.seeking) {
      const c = cuts.value.find((s) => v.currentTime >= s.start && v.currentTime < s.end - 0.01)
      if (c) v.currentTime = c.end
    }
  }
  raf = requestAnimationFrame(tick)
})
onUnmounted(() => cancelAnimationFrame(raf))

const seek = (t) => (video.value.currentTime = t)

function jump(dir) {
  const t = now.value
  const target = dir > 0
    ? cuts.value.find((c) => c.start > t + 0.05)
    : [...cuts.value].reverse().find((c) => c.start < t - 0.05)
  if (target) seek(target.start)
}

async function run(fn) {
  busy.value = true
  error.value = ''
  try { await fn() } catch (e) { error.value = e.message } finally { busy.value = false }
}

function download(ext, text, type) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type }))
  a.download = `${baseName(store.info.name)}_edl.${ext}`
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

const exportJson = () => download('json', JSON.stringify(store.edl, null, 2), 'application/json')
const exportCsv = () => download('csv',
  'no,start,end,duration,action\n' + store.edl.segments
    .map((s, i) => [i + 1, s.start, s.end, (s.end - s.start).toFixed(3), s.action].join(',')).join('\n'),
  'text/csv')
</script>

<template>
  <div class="row head">
    <div>
      <h1>Tinjau Potongan</h1>
      <p class="muted">
        {{ cuts.length }} potongan · durasi hasil {{ fmtTime(kept) }}
        ({{ Math.round((kept / duration) * 100) }}% dari asli). Ubah aksi tiap segmen bila perlu.
      </p>
    </div>
    <div class="spacer"></div>
    <div class="card stat"><span class="muted">Durasi asli</span><strong>{{ fmtTime(duration) }}</strong></div>
  </div>

  <div class="grid">
    <div>
      <video ref="video" :src="store.fileUrl" controls></video>
      <div class="row controls">
        <button title="Potongan sebelumnya" @click="jump(-1)">⏮</button>
        <button title="Potongan berikutnya" @click="jump(1)">⏭</button>
        <span class="muted">{{ fmtTime(now) }} / {{ fmtTime(duration) }}</span>
        <div class="spacer"></div>
        <button :class="{ primary: mode === 'result' }" @click="mode = 'result'">Hasil</button>
        <button :class="{ primary: mode === 'original' }" @click="mode = 'original'">Asli</button>
      </div>
    </div>
    <EdlTable :now="now" @seek="seek" />
  </div>

  <div class="card" style="margin-top: 24px">
    <AudioTimeline :now="now" @seek="seek" />
    <div class="row sliders">
      <div class="spacer">
        <label>Durasi jeda minimum: {{ store.params.min_silence.toFixed(2) }} s</label>
        <input v-model.number="store.params.min_silence" type="range" min="0.3" max="1.5" step="0.05" />
      </div>
      <div class="spacer">
        <label>Padding akhir: {{ store.params.pad_end.toFixed(2) }} s</label>
        <input v-model.number="store.params.pad_end" type="range" min="0.05" max="0.4" step="0.01" />
      </div>
      <button :disabled="busy" @click="run(analyze)">{{ busy ? 'Memproses...' : 'Analisis ulang' }}</button>
    </div>
  </div>

  <p v-if="error" class="error">{{ error }}</p>
  <div class="row footer">
    <button class="link" @click="store.step = 1">← Kembali ke pengaturan</button>
    <div class="spacer"></div>
    <button @click="exportJson">Ekspor EDL (.json)</button>
    <button @click="exportCsv">Ekspor EDL (.csv)</button>
    <button class="primary" :disabled="busy || !kept" @click="run(startRender)">Render Video →</button>
  </div>
</template>

<style scoped>
.head { align-items: flex-start; margin-bottom: 20px; }
.stat { display: flex; flex-direction: column; padding: 12px 20px; }
.stat strong { font-size: 22px; }
.controls { margin-top: 12px; }
.sliders { margin-top: 18px; gap: 24px; align-items: flex-end; }
.footer { margin-top: 24px; }
</style>
