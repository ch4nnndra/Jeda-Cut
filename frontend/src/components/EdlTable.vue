<script setup>
import { store, fmtTime } from '../store'

defineProps({ now: Number })
defineEmits(['seek'])
</script>

<template>
  <div class="card">
    <h3>Daftar Potongan (EDL)</h3>
    <div class="scroll">
      <table>
        <thead>
          <tr><th>No</th><th>Mulai</th><th>Selesai</th><th>Durasi</th><th>Aksi</th></tr>
        </thead>
        <tbody>
          <!-- Klik baris untuk melompat ke segmen. Ganti aksi langsung mengubah store.edl (reaktif ke timeline). -->
          <tr v-for="(s, i) in store.edl.segments" :key="i" @click="$emit('seek', s.start)"
              :class="{ cut: s.action === 'cut', active: now >= s.start && now < s.end }">
            <td>{{ i + 1 }}</td>
            <td>{{ fmtTime(s.start) }}</td>
            <td>{{ fmtTime(s.end) }}</td>
            <td>{{ (s.end - s.start).toFixed(2) }}s</td>
            <td>
              <select v-model="s.action" @click.stop>
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
.scroll { max-height: 420px; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--muted); font-weight: 500; position: sticky; top: 0; background: var(--panel); }
th, td { padding: 7px 6px; border-bottom: 1px solid var(--border); }
tr { cursor: pointer; }
tr.cut td:not(:last-child) { color: var(--cut); }
tr.active { background: var(--panel2); }
select { padding: 4px 6px; }

/* HP: tabel dipadatkan agar pilihan "Pertahankan" tidak terpotong, sisanya bisa digeser horizontal */
@media (max-width: 640px) {
  .scroll { overflow-x: auto; }
  table { font-size: 13px; }
  th, td { padding: 6px 3px; white-space: nowrap; }
  select { width: auto; padding: 4px; font-size: 13px; }
}
</style>
