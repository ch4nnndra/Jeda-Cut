<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { store, analyze, startRender, actionsOf, fmtTime, fmtLong } from '../store'
import EdlTable from '../components/EdlTable.vue'
import AudioTimeline from '../components/AudioTimeline.vue'

const video = ref(null)
const mode = ref('result')   // 'result' = lompati segmen cut, 'original' = putar apa adanya
const now = ref(0)
const busy = ref(false)
const error = ref('')

const duration = store.info.duration
const cuts = computed(() => store.edl.segments.filter((s) => s.action === 'cut'))
const kept = computed(() => store.edl.segments.reduce((t, s) => t + (s.action === 'keep' ? s.end - s.start : 0), 0))
const saved = computed(() => duration - kept.value)
const savedPct = computed(() => Math.round((saved.value / duration) * 100))
// Slider sudah digeser tapi belum dianalisis ulang: EDL masih memakai pengaturan lama.
const dirty = computed(() => ['min_silence', 'pad_end'].some((k) => store.params[k] !== store.edl.params[k]))
// Ada aksi di Daftar Potongan yang diubah manual dari hasil analisis.
const edited = computed(() => actionsOf(store.edl) !== store.autoActions)

function reanalyze() {
  if (edited.value && !confirm('Analisis ulang akan mengganti perubahan yang Anda buat di Daftar Potongan. Lanjutkan?')) return
  run(analyze)
}

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
</script>

<template>
  <div class="row head">
    <div>
      <h1>Periksa Hasil Potongan</h1>
      <!-- Hemat kurang dari 1 detik dianggap tidak ada jeda, agar tidak muncul "lebih singkat 0 detik" -->
      <template v-if="saved >= 1">
        <p class="lead">Video jadi lebih singkat {{ fmtLong(saved) }}.</p>
      </template>
      <template v-else>
        <p class="lead">Tidak ada jeda panjang yang perlu dipotong.</p>
        <p class="muted">Videonya sudah padat. Coba turunkan Durasi jeda minimum di bawah jika ingin memotong jeda yang lebih pendek.</p>
      </template>
    </div>
    <div class="spacer"></div>
    <div class="card stat">
      <span class="muted">Waktu dihemat</span>
      <strong>{{ fmtLong(saved) }}</strong>
      <span class="muted">{{ savedPct }}% lebih singkat</span>
    </div>
  </div>

  <!-- Grid area: desktop = video | tabel, timeline di bawah selebar penuh.
       HP = video, timeline, tabel, supaya timeline dekat dengan video saat menyesuaikan potongan. -->
  <div class="review">
    <div class="player">
      <video ref="video" :src="store.fileUrl" controls></video>
      <div class="row controls">
        <button title="Potongan sebelumnya" aria-label="Potongan sebelumnya" @click="jump(-1)">⏮</button>
        <button title="Potongan berikutnya" aria-label="Potongan berikutnya" @click="jump(1)">⏭</button>
        <span class="muted">{{ fmtTime(now) }} / {{ fmtTime(duration) }}</span>
        <div class="spacer"></div>
        <button :class="{ primary: mode === 'result' }" :aria-pressed="mode === 'result'"
                title="Putar tanpa bagian yang dipotong" @click="mode = 'result'">Hasil</button>
        <button :class="{ primary: mode === 'original' }" :aria-pressed="mode === 'original'"
                title="Putar video asli" @click="mode = 'original'">Asli</button>
      </div>
    </div>
    <EdlTable class="table" :now="now" @seek="seek" />

    <div class="card timeline">
      <AudioTimeline :now="now" @seek="seek" />
      <div class="row sliders">
        <label class="spacer field">Durasi jeda minimum: {{ store.params.min_silence.toFixed(2) }} s
          <input v-model.number="store.params.min_silence" type="range" min="0.3" max="1.5" step="0.05" />
        </label>
        <label class="spacer field">Padding akhir: {{ store.params.pad_end.toFixed(2) }} s
          <input v-model.number="store.params.pad_end" type="range" min="0.05" max="0.4" step="0.01" />
        </label>
        <button :class="{ primary: dirty }" :disabled="busy" @click="reanalyze">{{ busy ? 'Memproses...' : 'Analisis ulang' }}</button>
      </div>
      <p v-if="dirty" class="hint" role="status">Pengaturan berubah. Klik Analisis ulang untuk menerapkannya sebelum render.</p>
    </div>
  </div>

  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="row footer">
    <button @click="store.step = 1">← Kembali ke pengaturan</button>
    <div class="spacer"></div>
    <button class="primary" :disabled="busy || !kept" @click="run(startRender)">Render Video →</button>
  </div>
</template>

<style scoped>
.head { align-items: flex-start; margin-bottom: 20px; }
.review { display: grid; gap: 24px; align-items: start; grid-template-columns: minmax(0, 1fr) 380px;
  grid-template-areas: "player table" "timeline timeline"; }
.player { grid-area: player; }
.table { grid-area: table; }
.timeline { grid-area: timeline; }
@media (max-width: 900px) {
  .review { grid-template-columns: minmax(0, 1fr); grid-template-areas: "player" "timeline" "table"; }
}
.stat { display: flex; flex-direction: column; padding: 12px 20px; }
.stat strong { font-size: 22px; color: var(--ok); }
.lead { font-size: 18px; font-weight: 600; margin: 4px 0 2px; }
.head .muted { margin: 0; max-width: 720px; }
.hint { color: #ffd166; font-size: 14px; margin: 10px 0 0; }
.controls { margin-top: 12px; flex-wrap: nowrap; } /* tombol Hasil/Asli tetap satu baris */
.controls span { white-space: nowrap; }
.sliders { margin-top: 18px; gap: 24px; align-items: flex-end; }
.footer { margin-top: 24px; }
.footer button { padding: 12px 20px; }
/* Desktop: bilah aksi menempel di bawah layar, jadi Render bisa ditekan tanpa scroll ke dasar halaman */
@media (min-width: 641px) {
  .footer { position: sticky; bottom: 0; z-index: 5; padding: 14px 0; background: var(--bg);
    border-top: 1px solid var(--border); }
}

/* HP: slider dan tombol bawah ditumpuk satu per baris dengan lebar penuh */
@media (max-width: 640px) {
  .sliders > *, .footer > * { flex: 1 1 100%; }
  .footer .spacer { display: none; }
  .head .spacer, .stat { display: none; } /* durasi asli sudah ada di kalimat ringkasan */
  .head { margin-bottom: 12px; }
  video { max-height: 40vh; max-height: 40svh; }
  /* Preview menempel di atas saat digulir (seperti editor video di HP), jadi video dan timeline
     terlihat bersamaan ketika menyesuaikan potongan. */
  .player { position: sticky; top: 0; z-index: 4; background: var(--bg); padding-bottom: 8px; }
  .controls { gap: 6px; }
  .controls button { padding: 8px 11px; }
  .controls span { font-size: 13px; }
}
</style>
