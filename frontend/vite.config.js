// Vite build/dev-server config. `npm run dev` serves on :5173; `npm run build` writes dist/,
// which the Docker image serves with nginx (see Dockerfile and nginx.conf.template).
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // In dev, /api is forwarded to the backend so the browser sees one origin (cookies just work).
  const backend = env.DEV_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      host: true, // reachable from your phone on the same Wi-Fi
      proxy: { '/api': { target: backend, changeOrigin: false } },
    },
  }
})
