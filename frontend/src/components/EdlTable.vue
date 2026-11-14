<script setup>
import { computed, ref } from 'vue'
import { store, fmtTime } from '../store'

defineProps({ now: Number })
defineEmits(['seek'])

const cutsOnly = ref(false)
// Filter memakai hasil analisis awal juga, jadi baris yang baru diubah ke "Pertahankan" tidak langsung hilang.
const rows = computed(() => {
  const auto = store.autoActions.split(',')
  return store.edl.segments.map((s, i) => ({ s, i }))
    .filter(({ s, i }) => !cutsOnly.value || s.action === 'cut' || auto[i] === 'cut')
})
</script>

<template>
  <div class="card">
    <div class="row title">
      <h3>Daftar Potongan</h3>
      <div class="spacer"></div>
      <label class="check"><input v-model="cutsOnly" type="checkbox" /> Hanya yang dipotong</label>
    </div>
    <div class="scroll">
      <table>
        <thead>
          <tr><th>No</th><th>Mulai</th><th>Selesai</th><th>Durasi</th><th>Aksi</th></tr>
        </thead>
        <tbody>
          <!-- Klik baris untuk melompat ke segmen. Ganti aksi langsung mengubah store.edl (reaktif ke timeline). -->
          <tr v-for="{ s, i } in rows" :key="i" @click="$emit('seek', s.start)"
              :class="{ cut: s.action === 'cut', active: now >= s.start && now < s.end }">
            <td>{{ i + 1 }}</td>
            <!-- Waktu mulai berupa tombol supaya lompat ke segmen juga bisa lewat keyboard -->
            <td><button class="time" :aria-label="`Putar segmen ${i + 1} dari ${fmtTime(s.start)}`"
                        @click.stop="$emit('seek', s.start)">{{ fmtTime(s.start) }}</button></td>
            <td>{{ fmtTime(s.end) }}</td>
            <td>{{ (s.end - s.start).toFixed(2) }}s</td>
            <td>
              <select v-model="s.action" :aria-label="`Aksi segmen ${i + 1}`" @click.stop>
                <option value="keep">Pertahankan</option>
                <option value="cut">Potong</option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.title { margin-bottom: 10px; }
.title h3 { margin: 0; }
.check { display: flex; gap: 6px; align-items: center; color: var(--text); font-size: 14px; }
.scroll { max-height: 420px; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--muted); font-weight: 500; position: sticky; top: 0; background: var(--panel); }
th, td { padding: 7px 6px; border-bottom: 1px solid var(--border); }
tr { cursor: pointer; }
tr.cut td:not(:last-child) { color: var(--cut-text); }
tr.active { background: var(--panel2); }
select { padding: 4px 6px; }
.time { background: none; border: 0; padding: 0; color: inherit; text-decoration: underline dotted; text-underline-offset: 3px; }

/* HP: tabel dipadatkan agar pilihan "Pertahankan" tidak terpotong, sisanya bisa digeser horizontal */
@media (max-width: 640px) {
  .scroll { overflow-x: auto; }
  table { font-size: 13px; }
  th, td { padding: 6px 3px; white-space: nowrap; }
  select { width: auto; padding: 4px; font-size: 13px; }
}
</style>
