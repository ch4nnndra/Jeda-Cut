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
  const { energy, step, upper, lower, noise_floor } = store.timeline
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
    // Label tiap garis diberi posisi x berbeda karena nilainya sering hanya selisih beberapa dB.
    const line = (db, color, dash, text, lx) => {
      ctx.strokeStyle = color
      ctx.setLineDash(dash)
      ctx.beginPath(); ctx.moveTo(0, y(db)); ctx.lineTo(w, y(db)); ctx.stroke()
      ctx.fillStyle = '#000a'
      ctx.fillRect(lx - 3, y(db) - 15, ctx.measureText(text).width + 6, 14)
      ctx.fillStyle = color
      ctx.fillText(text, lx, y(db) - 4)
    }
    ctx.font = '11px system-ui'
    line(upper, '#ffd166', [6, 4], `threshold atas ${upper.toFixed(1)} dB`, 6)
    line(lower, '#f4a261', [3, 3], `threshold bawah ${lower.toFixed(1)} dB`, 170)
    line(noise_floor, '#c0c6d0', [1, 3], `noise floor ${noise_floor.toFixed(1)} dB`, 350)
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
    <h3 style="margin: 0">Timeline Audio</h3>
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
  </div>
</template>

<style scoped>
.wrap { overflow-x: auto; margin-top: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); }
.inner { position: relative; }
canvas { display: block; width: 100%; height: 190px; cursor: pointer; }
.playhead { position: absolute; top: 0; height: 170px; width: 2px; background: #fff; pointer-events: none; }
.check { display: flex; gap: 6px; align-items: center; color: var(--text); font-size: 14px; }
.legend { gap: 20px; margin-top: 8px; font-size: 13px; color: var(--muted); }
.sw { display: inline-block; width: 12px; height: 12px; vertical-align: -1px; margin-right: 4px; }
.sw.speech { background: var(--accent); }
.sw.cut { background: repeating-linear-gradient(45deg, var(--cut) 0 2px, transparent 2px 5px); border: 1px solid var(--cut); }
</style>
