import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El backend, visto desde esta máquina. Solo lo usa el proxy de
// desarrollo; en producción el propio backend sirve el frontend y no hay
// dos puertos que conciliar.
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8080'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,

    // Sin esto habría que decirle al frontend en qué host está el API, y
    // esa dirección cambia según desde dónde se entre: localhost en esta
    // máquina, otra IP en la red local, otro nombre a través del túnel.
    // Con el proxy el frontend siempre pide a su propio origen.
    proxy: {
      '/api':    { target: BACKEND, changeOrigin: true },
      '/public': { target: BACKEND, changeOrigin: true },
      '/media':  { target: BACKEND, changeOrigin: true },
    },
  },
})
