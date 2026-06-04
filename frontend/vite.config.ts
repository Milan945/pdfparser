import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    // Allow access through ngrok / other tunnels (Vite blocks unknown Host headers by default).
    allowedHosts: true,
    // HMR websocket must connect over the tunnel's https port.
    hmr: { clientPort: 443 },
    proxy: {
      '/upload': 'http://localhost:8000',
      '/pdf': 'http://localhost:8000',
      '/session': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'node',
  },
})
