/** Runtime configuration resolved from Vite env variables at build time. */
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
} as const
