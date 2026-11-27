import axios, { type AxiosRequestConfig } from 'axios'
import { config } from '../config'
import { toApiError } from './errors'

/** Decimal values (money, decimal quantities) arrive from DRF as strings; never use floats. */
export type Money = string

/** DRF PageNumberPagination envelope (data-model.md#paginatedt). */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type ListParams = {
  page?: number
  search?: string
  ordering?: string
} & Record<string, string | number | boolean | undefined>

/** Auth endpoints report 401 as part of their normal flow; they never signal "session ended". */
const AUTH_FLOW_PATHS = ['/auth/login/', '/auth/me/', '/auth/logout/', '/auth/csrf/']

let unauthenticatedHandler: (() => void) | null = null
let unauthenticatedNotified = false

/**
 * Registers the callback run when a request reports the session is gone (401).
 * It runs once per session: the latch resets only after a successful sign-in, so
 * responses still in flight from before the expiry can't trigger it again.
 */
export function setUnauthenticatedHandler(fn: (() => void) | null): void {
  unauthenticatedHandler = fn
  unauthenticatedNotified = false
}

export const http = axios.create({
  baseURL: config.apiBaseUrl,
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  timeout: 15_000,
  headers: { Accept: 'application/json' },
})

http.interceptors.response.use(
  (response) => {
    if (response.config.url?.endsWith('/auth/login/')) unauthenticatedNotified = false
    return response
  },
  (error: unknown) => {
    const apiError = toApiError(error)
    const url = axios.isAxiosError(error) ? (error.config?.url ?? '') : ''
    const isAuthFlow = AUTH_FLOW_PATHS.some((path) => url.endsWith(path))
    if (apiError.kind === 'unauthenticated' && !isAuthFlow && !unauthenticatedNotified) {
      unauthenticatedNotified = true
      unauthenticatedHandler?.()
    }
    return Promise.reject(apiError)
  },
)

function cleanParams(params?: object): Record<string, unknown> | undefined {
  if (!params) return undefined
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined))
}

export async function apiGet<T>(url: string, params?: object, options?: AxiosRequestConfig): Promise<T> {
  const response = await http.get<T>(url, { ...options, params: cleanParams(params) })
  return response.data
}

export function apiGetPage<T>(url: string, params?: ListParams, options?: AxiosRequestConfig): Promise<Paginated<T>> {
  return apiGet<Paginated<T>>(url, params, options)
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const response = await http.post<T>(url, body)
  return response.data
}

export async function apiPatch<T>(url: string, body: unknown): Promise<T> {
  const response = await http.patch<T>(url, body)
  return response.data
}

export async function apiPut<T>(url: string, body: unknown): Promise<T> {
  const response = await http.put<T>(url, body)
  return response.data
}

/** Most deletes return 204 (`void`); some return the updated parent record. */
export async function apiDelete<T = void>(url: string): Promise<T> {
  const response = await http.delete<T>(url)
  return response.data
}
