/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the API; keep same-origin (default `/api`). */
  readonly VITE_API_BASE_URL?: string
  /** Dev-server proxy target for `/api` (vite.config.ts only). */
  readonly VITE_DEV_API_TARGET?: string
  /** IANA time zone for displaying dates (default Asia/Manila). */
  readonly VITE_STORE_TIME_ZONE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
