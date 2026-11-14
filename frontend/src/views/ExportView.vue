<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { store, API, api, resetAll, fmtLong, fmtSize } from '../store'

const st = ref({ status: 'rendering', progress: 0 })
const id = store.info.id
const outUrl = `${API}/download/${id}`
const outName = store.info.name.replace(/\.[^.]+$/, '') + '_jumpcut.mp4'
const stamp = Date.now() // cache-buster agar render ulang tidak memutar file lama
const eta = ref('')
const cancelling = ref(false)

// Render bisa beberapa menit, jadi status ditanyakan ke server tiap 1 detik sampai selesai.
async function poll() {
  try { st.value = await api(`/status/${id}`) } catch (e) { st.value = { status: 'error', error: e.message } }
  // Perkiraan sisa waktu dari laju progres sejauh ini. Baru ditampilkan setelah 3% agar angkanya tidak melompat-lompat.
  const pct = st.value.progress || 0
  if (pct >= 3 && pct < 100) {
    const left = ((Date.now() - stamp) / 1000) * (100 - pct) / pct
    eta.value = left < 60 ? 'kurang dari 1 menit' : `sekitar ${Math.round(left / 60)} menit`
  }
  if (st.value.status === 'cancelled') store.step = 2
  if (st.value.status !== 'rendering') clearInterval(timer)
}
const timer = setInterval(poll, 1000)
poll()
onUnmounted(() => clearInterval(timer))

async function cancel() {
  cancelling.value = true
  try {
    // Server baru menjawab setelah render benar-benar berhenti, jadi bisa langsung kembali ke Periksa.
    const r = await api(`/cancel/${id}`, 'POST')
    if (r.status === 'cancelled') store.step = 2
  } catch {
    // Render keburu selesai: server menolak pembatalan, poll berikutnya menampilkan hasilnya.
  }
}

const orig = store.info.duration
const ratio = computed(() => (st.value.out_duration || 0) / orig)
const saved = computed(() => orig - (st.value.out_duration || 0))
const p = store.edl.params
const summary = computed(() => [
  ['Durasi jeda minimum', `${p.min_silence} s`],
  ['Durasi suara minimum', `${p.min_speech} s`],
  ['Padding awal / akhir', `${p.pad_start} / ${p.pad_end} s`],
  ['Threshold', 'Adaptif (otomatis)'],
  ['Crossfade audio', `${p.audio_crossfade_ms} ms`],
  ['Encoder', st.value.encoder || (store.info.has_video ? p.encoder : 'tanpa video')],
])
</script>

<template>
  <template v-if="st.status === 'rendering'">
    <h1>{{ cancelling ? 'Membatalkan...' : 'Menyusun video...' }}</h1>
    <p class="muted">Jeda sedang dihapus dan video disusun ulang. Biarkan halaman ini tetap terbuka, kemajuannya diperbarui otomatis.</p>
    <div class="bar big" role="progressbar" aria-label="Kemajuan menyusun video" aria-valuemin="0" aria-valuemax="100"
         :aria-valuenow="Math.round(st.progress || 0)">
      <div :style="{ width: (st.progress || 0) + '%' }"></div>
    </div>
    <div class="row progress-info">
      <strong aria-hidden="true">{{ (st.progress || 0).toFixed(0) }}%</strong>
      <span v-if="eta" class="muted">Perkiraan sisa {{ eta }}</span>
      <div class="spacer"></div>
      <button :disabled="cancelling" @click="cancel">Batalkan</button>
    </div>
  </template>

  <template v-else-if="st.status === 'error'">
    <h1>Video gagal disusun</h1>
    <p role="alert">Terjadi masalah saat menyusun video. Coba render ulang. Kalau tetap gagal, unggah ulang videonya.</p>
    <details class="card tech"><summary>Detail teknis</summary><pre class="error">{{ st.error }}</pre></details>
    <button class="primary" @click="store.step = 2">← Kembali ke pemeriksaan</button>
  </template>

  <template v-else>
    <div class="row head">
      <div class="done-icon">✓</div>
      <div>
        <h1>Video siap</h1>
        <p class="muted">Lebih singkat {{ fmtLong(saved) }} ({{ Math.round((1 - ratio) * 100) }}%) dari video asli.</p>
      </div>
    </div>

    <div class="grid">
      <div>
        <video :src="`${outUrl}?t=${stamp}`" controls></video>
        <div class="card row file">
          <div class="badge">MP4</div>
          <div class="spacer">
            <strong>{{ outName }}</strong>
            <div class="muted">{{ fmtSize(st.out_size) }} (asli {{ fmtSize(st.size) }}) · {{ fmtLong(st.out_duration) }}</div>
          </div>
          <a class="btn primary" :href="outUrl" :download="outName">Unduh video</a>
        </div>
      </div>

      <div class="side">
        <div class="card">
          <span class="muted">Waktu dihemat</span>
          <div class="saved">{{ fmtLong(saved) }}</div>
          <span class="caption">Asli · {{ fmtLong(orig) }}</span>
          <div class="bar"><div style="width: 100%; background: var(--muted)"></div></div>
          <span class="caption">Hasil · {{ fmtLong(st.out_duration) }}</span>
          <div class="bar hatched"><div :style="{ width: ratio * 100 + '%' }"></div></div>
        </div>

        <div class="card">
          <h3>Pengaturan yang Dipakai</h3>
          <div v-for="[k, v] in summary" :key="k" class="row kv"><span class="muted">{{ k }}</span><span>{{ v }}</span></div>
        </div>

        <button class="primary block" @click="resetAll">Proses Video Baru</button>
        <button class="block" @click="store.step = 2">Ubah potongan &amp; render ulang</button>
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
.saved { font-size: 28px; font-weight: 700; margin: 4px 0 14px; color: var(--ok); }
.progress-info { margin-top: 12px; }
.tech { margin: 16px 0; }
.tech summary { cursor: pointer; color: var(--muted); }
.side .bar { margin: 4px 0 12px; }
.caption { display: block; font-size: 13px; color: var(--muted); }
.hatched { background: repeating-linear-gradient(45deg, var(--panel2) 0 4px, var(--border) 4px 8px); }
.kv { justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
pre { white-space: pre-wrap; }
.file .spacer { min-width: 0; overflow-wrap: anywhere; } /* nama file panjang dipatah, tidak melebar */

@media (max-width: 640px) {
  .file .btn { flex: 1 1 100%; }
  .done-icon { width: 44px; height: 44px; font-size: 20px; }
  .saved { font-size: 24px; }
}
</style>
