<script setup>
import { computed } from 'vue'
import { store } from '../store'

defineProps({ disabled: Boolean, busy: Boolean })
defineEmits(['analyze', 'render'])

const p = store.params
// Kartu preset berubah jadi "Diubah" begitu ada satu nilai yang beda dari Default.
const isDefault = computed(() => Object.keys(store.defaults).every((k) => p[k] === store.defaults[k]))
const reset = () => Object.assign(p, store.defaults)
</script>

<template>
  <aside class="card">
    <h3>Pengaturan Trim</h3>

    <label>Preset</label>
    <button class="preset" :class="{ primary: isDefault }" :disabled="isDefault" @click="reset">
      <span>{{ isDefault ? 'Default' : 'Diubah' }}</span>
      <span>{{ isDefault ? '✓' : 'klik untuk kembali ke Default' }}</span>
    </button>

    <div class="mode"><span class="muted">Mode</span><strong>Trim jeda</strong></div>

    <details open>
      <summary>Pengaturan lanjutan</summary>
      <div class="fields">
        <div><label>Durasi jeda minimum (s)</label><input v-model.number="p.min_silence" type="number" step="0.05" min="0.1" max="5" /></div>
        <div><label>Durasi suara minimum (s)</label><input v-model.number="p.min_speech" type="number" step="0.05" min="0" max="2" /></div>
        <div><label>Padding awal (s)</label><input v-model.number="p.pad_start" type="number" step="0.01" min="0" max="1" /></div>
        <div><label>Padding akhir (s)</label><input v-model.number="p.pad_end" type="number" step="0.01" min="0" max="1" /></div>
        <div><label>Crossfade audio (ms)</label><input v-model.number="p.audio_crossfade_ms" type="number" step="1" min="0" max="50" /></div>
        <div>
          <label>Metode threshold</label>
          <select v-model="p.threshold_method">
            <option value="stat">Statistik</option>
            <option value="dual">Dual threshold</option>
            <option value="midpoint">Midpoint</option>
          </select>
        </div>
      </div>
      <label class="check"><input v-model="p.video_crossfade" type="checkbox" /> Crossfade video (3 frame)</label>
      <label>Encoder</label>
      <select v-model="p.encoder">
        <option value="auto">Otomatis (h264_nvenc jika GPU mendukung)</option>
        <option value="h264_nvenc">h264_nvenc</option>
        <option value="libx264">libx264 (CRF 20)</option>
      </select>
    </details>

    <button class="primary block" :disabled="disabled" @click="$emit('analyze')">
      {{ busy ? 'Menganalisis...' : 'Analisis Audio →' }}
    </button>
    <button class="block" :disabled="disabled" style="margin-top: 10px" @click="$emit('render')">
      Analisis &amp; Render Langsung
    </button>
  </aside>
</template>

<style scoped>
.preset { width: 100%; display: flex; justify-content: space-between; margin: 6px 0 14px; }
.preset:disabled { opacity: 1; }
.mode { display: flex; justify-content: space-between; border: 1px dashed var(--border); border-radius: 8px; padding: 10px 14px; }
details { border-top: 1px solid var(--border); margin: 18px 0; padding-top: 14px; }
summary { cursor: pointer; font-weight: 600; margin-bottom: 12px; }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.check { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; color: var(--text); font-size: 15px; }
</style>
