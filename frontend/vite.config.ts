import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react()],
    server: {
      // Same-origin API in development: cookies, CSRF and SameSite work without CORS
      // (research R4). Production serves /api from the same origin via a reverse proxy.
      proxy: {
        '/api': {
          target: env.VITE_DEV_API_TARGET || 'http://localhost:8000',
          changeOrigin: false,
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['src/test/setup.ts'],
      css: false,
      // Tests must not depend on a developer's local .env (same-origin API, research R4).
      env: { VITE_API_BASE_URL: '/api' },
    },
  }
})
