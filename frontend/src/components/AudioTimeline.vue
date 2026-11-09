<script setup>
import { onMounted, onUnmounted, ref, watchEffect } from 'vue'
import { store, fmtTime } from '../store'

defineProps({ now: Number })
const emit = defineEmits(['seek'])

const canvas = ref(null)
const showLines = ref(true)
const zoom = ref(1)
const H = 170        // tinggi area gambar
const AXIS = 20      // ruang label waktu di bawah
const duration = store.info.duration

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

// Garis threshold. Warna dan pola dipakai bersama oleh canvas dan legenda.
const LINES = [
  { key: 'upper', label: 'threshold atas', color: '#ffd166', dash: [6, 4], css: 'dashed' },
  { key: 'lower', label: 'threshold bawah', color: '#f4a261', dash: [3, 3], css: 'dashed' },
  { key: 'noise_floor', label: 'noise floor', color: '#c0c6d0', dash: [1, 3], css: 'dotted' },
]

// Pola arsiran diagonal untuk wilayah yang dipotong.
function hatch(ctx, color) {
  const c = document.createElement('canvas')
  c.width = c.height = 8
  const g = c.getContext('2d')
  g.strokeStyle = color
  g.beginPath(); g.moveTo(0, 8); g.lineTo(8, 0); g.stroke()
  return ctx.createPattern(c, 'repeat')
}

function draw() {
  const el = canvas.value
  if (!el) return
  const { energy, step, noise_floor } = store.timeline
  const segments = store.edl.segments.map((s) => [s.start, s.end, s.action]) // dibaca di sini agar watchEffect ikut melacak perubahan aksi
  const showL = showLines.value
  zoom.value // dilacak agar ukuran canvas digambar ulang saat zoom

  // Ukuran asli canvas dikali devicePixelRatio supaya tidak buram di layar HiDPI.
  // Lebar canvas dibatasi ~32000 px (batas browser), jadi dpr diturunkan saat zoom besar.
  const w = el.clientWidth
  const dpr = Math.min(window.devicePixelRatio || 1, 32000 / w)
  el.width = w * dpr
  el.height = (H + AXIS) * dpr
  const ctx = el.getContext('2d')
  ctx.scale(dpr, dpr)

  // Skala vertikal: dari sedikit di bawah noise floor sampai 0 dB.
  const lo = noise_floor - 6
  const y = (db) => H - Math.max(0, Math.min(1, (db - lo) / (0 - lo))) * H
  const x = (t) => (t / duration) * w

  ctx.fillStyle = css('--cut') + '22'
  for (const [s, e, a] of segments) if (a === 'cut') ctx.fillRect(x(s), 0, x(e) - x(s), H)
  ctx.fillStyle = hatch(ctx, css('--cut') + '88')
  for (const [s, e, a] of segments) if (a === 'cut') ctx.fillRect(x(s), 0, x(e) - x(s), H)

  // Batang energi per 100 ms.
  ctx.fillStyle = css('--accent')
  const bw = Math.max(1, x(step) - 0.5)
  energy.forEach((db, i) => ctx.fillRect(x(i * step), y(db), bw, H - y(db)))

  if (showL) {
    // Nilai tiap garis ditulis di legenda (HTML), bukan di canvas, agar tidak saling tumpuk di layar sempit.
    for (const { key, color, dash } of LINES) {
      const ly = y(store.timeline[key])
      ctx.strokeStyle = color
      ctx.setLineDash(dash)
      ctx.beginPath(); ctx.moveTo(0, ly); ctx.lineTo(w, ly); ctx.stroke()
    }
    ctx.setLineDash([])
  }

  // Label waktu: pilih interval terkecil yang jarak antar labelnya minimal 80 px.
  const tick = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800].find((t) => x(t) >= 80) || 3600
  ctx.fillStyle = css('--muted')
  ctx.font = '11px system-ui'
  for (let t = 0; t <= duration; t += tick) ctx.fillText(fmtTime(t).replace('.0', ''), x(t) + 2, H + 14)
}

// flush 'post': gambar setelah DOM diperbarui, supaya clientWidth sudah mengikuti zoom baru.
watchEffect(draw, { flush: 'post' })
onMounted(() => window.addEventListener('resize', draw))
onUnmounted(() => window.removeEventListener('resize', draw))

function onClick(e) {
  const r = canvas.value.getBoundingClientRect()
  emit('seek', ((e.clientX - r.left) / r.width) * duration)
}
</script>

<template>
  <div class="row">
    <h3 style="margin: 0; white-space: nowrap">Timeline Audio</h3>
    <div class="spacer"></div>
    <label class="check"><input v-model="showLines" type="checkbox" /> Garis threshold</label>
    <button @click="zoom = Math.max(1, zoom / 2)">−</button>
    <button @click="zoom = Math.min(16, zoom * 2)">+</button>
  </div>
  <div class="wrap">
    <div class="inner" :style="{ width: zoom * 100 + '%' }">
      <canvas ref="canvas" @click="onClick"></canvas>
      <!-- Playhead dibuat div terpisah agar canvas tidak perlu digambar ulang setiap frame. -->
      <div class="playhead" :style="{ left: (now / duration) * 100 + '%' }"></div>
    </div>
  </div>
  <div class="row legend">
    <span><i class="sw speech"></i> Suara</span>
    <span><i class="sw cut"></i> Jeda dipotong</span>
    <template v-if="showLines">
      <span v-for="l in LINES" :key="l.key">
        <i class="ln" :style="{ borderTopColor: l.color, borderTopStyle: l.css }"></i>
        {{ l.label }} {{ store.timeline[l.key].toFixed(1) }} dB
      </span>
    </template>
  </div>
</template>

<style scoped>
.wrap { overflow-x: auto; margin-top: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); }
.inner { position: relative; }
canvas { display: block; width: 100%; height: 190px; cursor: pointer; }
.playhead { position: absolute; top: 0; height: 170px; width: 2px; background: #fff; pointer-events: none; }
.check { display: flex; gap: 6px; align-items: center; color: var(--text); font-size: 14px; }
.legend { gap: 6px 20px; margin-top: 8px; font-size: 13px; color: var(--muted); }
.ln { display: inline-block; width: 18px; border-top: 2px dashed; vertical-align: middle; margin-right: 4px; }
.sw { display: inline-block; width: 12px; height: 12px; vertical-align: -1px; margin-right: 4px; }
.sw.speech { background: var(--accent); }
.sw.cut { background: repeating-linear-gradient(45deg, var(--cut) 0 2px, transparent 2px 5px); border: 1px solid var(--cut); }
</style>
