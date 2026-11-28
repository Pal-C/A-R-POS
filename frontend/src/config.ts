/** Runtime configuration resolved from Vite env variables at build time. */
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  /**
   * Shop default prices pre-filled on a new stringing order; staff can override
   * them per order (specs/007 R2). Plain amounts, e.g. "350.00".
   */
  stringingDefaults: {
    servicePrice: import.meta.env.VITE_STRINGING_SERVICE_PRICE || '350.00',
    stencilPrice: import.meta.env.VITE_STRINGING_STENCIL_PRICE || '50.00',
    gripPrice: import.meta.env.VITE_STRINGING_GRIP_PRICE || '120.00',
    storeStringDiscount: import.meta.env.VITE_STRINGING_STORE_STRING_DISCOUNT || '100.00',
  },
} as const
