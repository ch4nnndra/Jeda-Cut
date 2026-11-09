<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { store, API, api, resetAll, fmtTime, fmtSize, baseName } from '../store'

const st = ref({ status: 'rendering', progress: 0 })
const id = store.info.id
const outUrl = `${API}/download/${id}`
const outName = `${baseName(store.info.name)}_jumpcut.mp4`
const stamp = Date.now() // cache-buster agar render ulang tidak memutar file lama

// Render bisa beberapa menit, jadi status ditanyakan ke server tiap 1 detik sampai selesai.
async function poll() {
  try { st.value = await api(`/status/${id}`) } catch (e) { st.value = { status: 'error', error: e.message } }
  if (st.value.status !== 'rendering') clearInterval(timer)
}
const timer = setInterval(poll, 1000)
poll()
onUnmounted(() => clearInterval(timer))

const orig = store.info.duration
const ratio = computed(() => (st.value.out_duration || 0) / orig)
const p = store.edl.params
const methods = { midpoint: 'Midpoint', dual: 'Dual threshold' }
const summary = computed(() => [
  ['Durasi jeda minimum', `${p.min_silence} s`],
  ['Durasi suara minimum', `${p.min_speech} s`],
  ['Padding awal / akhir', `${p.pad_start} / ${p.pad_end} s`],
  ['Metode threshold', methods[p.threshold_method]],
  ['Crossfade audio', `${p.audio_crossfade_ms} ms`],
  ['Crossfade video', p.video_crossfade ? '3 frame' : 'Nonaktif'],
  ['Encoder', st.value.encoder || (store.info.has_video ? p.encoder : 'tanpa video')],
])
</script>

<template>
  <template v-if="st.status === 'rendering'">
    <h1>Merender video...</h1>
    <p class="muted">FFmpeg sedang memotong dan meng-encode ulang video. Halaman ini diperbarui otomatis.</p>
    <div class="bar big"><div :style="{ width: (st.progress || 0) + '%' }"></div></div>
    <p>{{ (st.progress || 0).toFixed(0) }}%</p>
  </template>

  <template v-else-if="st.status === 'error'">
    <h1>Render gagal</h1>
    <pre class="card error">{{ st.error }}</pre>
    <button @click="store.step = 2">← Kembali ke Tinjau</button>
  </template>

  <template v-else>
    <div class="row head">
      <div class="done-icon">✓</div>
      <div>
        <h1>Render selesai</h1>
        <p class="muted">Durasi berkurang {{ fmtTime(orig - st.out_duration) }} ({{ Math.round((1 - ratio) * 100) }}%).</p>
      </div>
    </div>

    <div class="grid">
      <div>
        <video :src="`${outUrl}?t=${stamp}`" controls></video>
        <div class="card row file">
          <div class="badge">MP4</div>
          <div class="spacer">
            <strong>{{ outName }}</strong>
            <div class="muted">{{ fmtSize(st.out_size) }} (asli {{ fmtSize(st.size) }}) · {{ fmtTime(st.out_duration) }}</div>
          </div>
          <a class="btn primary" :href="outUrl" :download="outName">Unduh video</a>
        </div>
      </div>

      <div class="side">
        <div class="card">
          <span class="muted">Durasi yang dipangkas</span>
          <div class="saved">{{ fmtTime(orig - st.out_duration) }}</div>
          <label>Asli · {{ fmtTime(orig) }}</label>
          <div class="bar"><div style="width: 100%; background: var(--muted)"></div></div>
          <label>Hasil · {{ fmtTime(st.out_duration) }}</label>
          <div class="bar hatched"><div :style="{ width: ratio * 100 + '%' }"></div></div>
        </div>

        <div class="card">
          <h3>Pengaturan yang Dipakai</h3>
          <div v-for="[k, v] in summary" :key="k" class="row kv"><span class="muted">{{ k }}</span><span>{{ v }}</span></div>
        </div>

        <button class="primary block" @click="resetAll">Proses Video Baru</button>
        <button class="block" @click="store.step = 2">Kembali &amp; Render Ulang</button>
      </div>
    </div>
  </template>
</template>

<style scoped>
.head { margin-bottom: 20px; gap: 16px; }
.done-icon { width: 56px; height: 56px; border-radius: 50%; border: 2px solid var(--ok); color: var(--ok);
  display: grid; place-items: center; font-size: 24px; }
.big { height: 16px; margin-top: 24px; }
.file { margin-top: 16px; gap: 16px; }
.badge { border: 1px solid var(--border); border-radius: 8px; padding: 14px 10px; font-size: 13px; }
.side { display: flex; flex-direction: column; gap: 16px; }
.saved { font-size: 34px; font-weight: 700; margin: 4px 0 14px; }
.side .bar { margin: 4px 0 12px; }
.hatched { background: repeating-linear-gradient(45deg, var(--panel2) 0 4px, var(--border) 4px 8px); }
.kv { justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
pre { white-space: pre-wrap; }
.file .spacer { min-width: 0; overflow-wrap: anywhere; } /* nama file panjang dipatah, tidak melebar */

@media (max-width: 640px) {
  .file .btn { flex: 1 1 100%; }
  .done-icon { width: 44px; height: 44px; font-size: 20px; }
  .saved { font-size: 28px; }
}
</style>
