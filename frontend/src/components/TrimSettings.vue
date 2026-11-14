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

    <span class="caption">Preset</span>
    <button class="preset" :class="{ primary: isDefault }" :disabled="isDefault" @click="reset">
      <span>{{ isDefault ? 'Default' : 'Diubah' }}</span>
      <span>{{ isDefault ? '✓' : 'klik untuk kembali ke Default' }}</span>
    </button>

    <div class="mode"><span class="muted">Mode</span><strong>Trim jeda otomatis</strong></div>

    <!-- Ditutup secara bawaan: nilai Default sudah teruji, jadi pengguna tidak perlu mengatur apa pun -->
    <details>
      <summary>Pengaturan lanjutan</summary>
      <div class="fields">
        <label class="field">Durasi jeda minimum (s)<input v-model.number="p.min_silence" type="number" step="0.05" min="0.1" max="5" /></label>
        <label class="field">Durasi suara minimum (s)<input v-model.number="p.min_speech" type="number" step="0.05" min="0" max="2" /></label>
        <label class="field">Padding awal (s)<input v-model.number="p.pad_start" type="number" step="0.01" min="0" max="1" /></label>
        <label class="field">Padding akhir (s)<input v-model.number="p.pad_end" type="number" step="0.01" min="0" max="1" /></label>
        <label class="field">Crossfade audio (ms)<input v-model.number="p.audio_crossfade_ms" type="number" step="1" min="0" max="50" /></label>
        <label class="field">Encoder
          <select v-model="p.encoder">
            <option value="auto">Otomatis</option>
            <option value="h264_nvenc">h264_nvenc</option>
            <option value="libx264">libx264 (CRF 20)</option>
          </select>
        </label>
      </div>
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
.caption { font-size: 13px; color: var(--muted); }
.preset { width: 100%; display: flex; justify-content: space-between; margin: 6px 0 14px; }
.preset:disabled { opacity: 1; cursor: default; }
/* Info statis (bukan kontrol): latar polos tanpa garis putus-putus supaya tidak terlihat bisa diklik */
.mode { display: flex; justify-content: space-between; background: var(--panel2); border-radius: 8px; padding: 10px 14px; }
details { border-top: 1px solid var(--border); margin: 18px 0; padding-top: 14px; }
summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
details[open] summary { margin-bottom: 12px; }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
</style>
