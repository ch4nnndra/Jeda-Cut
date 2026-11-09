import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Saat development, request /api diteruskan ke server FastAPI di port 8000.
export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
