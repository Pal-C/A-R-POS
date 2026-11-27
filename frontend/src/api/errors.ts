import axios from 'axios'

/** Every failure a screen can receive from the API layer (data-model.md#apierror). */
export type ApiErrorKind =
  | 'validation'
  | 'unauthenticated'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'rate_limited'
  | 'network'
  | 'unexpected'

export const MESSAGES = {
  network: 'Cannot reach the server. Check the connection and try again.',
  validation: 'Please correct the highlighted fields.',
  unauthenticated: 'Your session has ended. Please sign in again.',
  forbidden: "You don't have permission to do that.",
  not_found: 'Not found.',
  conflict: 'This record changed. Reload and try again.',
  unexpected: 'Something went wrong. Please try again.',
} as const

export type FieldErrors = Record<string, string[]>

interface ApiErrorInit {
  kind: ApiErrorKind
  status: number | null
  message: string
  fieldErrors?: FieldErrors
  nonFieldErrors?: string[]
}

/** A normalized, display-safe API failure. `message` never contains server internals. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly fieldErrors: FieldErrors
  readonly nonFieldErrors: string[]

  constructor(init: ApiErrorInit) {
    super(init.message)
    this.name = 'ApiError'
    this.kind = init.kind
    this.status = init.status
    this.fieldErrors = init.fieldErrors ?? {}
    this.nonFieldErrors = init.nonFieldErrors ?? []
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError
}

const TOP_LEVEL_NON_FIELD_KEYS = new Set(['non_field_errors', 'detail'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Flattens DRF's nested error payload into dotted keys, e.g. `items.0.quantity`. */
export function flattenFieldErrors(data: unknown, prefix = ''): FieldErrors {
  const out: FieldErrors = {}
  const add = (key: string, message: string) => {
    ;(out[key] ??= []).push(message)
  }
  const walk = (value: unknown, path: string) => {
    if (typeof value === 'string') {
      add(path, value)
    } else if (Array.isArray(value)) {
      value.forEach((item, index) => {
        if (typeof item === 'string') add(path, item)
        else walk(item, `${path}.${index}`)
      })
    } else if (isRecord(value)) {
      for (const [key, child] of Object.entries(value)) {
        walk(child, path ? `${path}.${key}` : key)
      }
    }
  }

  if (isRecord(data)) {
    for (const [key, value] of Object.entries(data)) {
      if (!prefix && TOP_LEVEL_NON_FIELD_KEYS.has(key)) continue
      walk(value, prefix ? `${prefix}.${key}` : key)
    }
  }
  return out
}

function stringList(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.filter((v): v is string => typeof v === 'string')
  return []
}

function nonFieldErrorsOf(data: unknown): string[] {
  if (Array.isArray(data)) return stringList(data)
  if (!isRecord(data)) return []
  return [...stringList(data.non_field_errors), ...stringList(data.detail)]
}

function retryAfterMessage(header: unknown): string {
  const seconds = Number(header)
  return Number.isFinite(seconds) && seconds > 0
    ? `Too many attempts. Try again in ${Math.ceil(seconds)} seconds.`
    : 'Too many attempts. Try again later.'
}

function unexpected(status: number | null, cause: unknown): ApiError {
  // Technical details go to the developer console only (spec US4-3, SC-005).
  console.error('Unexpected API error', cause)
  return new ApiError({ kind: 'unexpected', status, message: MESSAGES.unexpected })
}

/** Converts anything thrown by the HTTP layer into an `ApiError`. Pure apart from logging. */
export function toApiError(err: unknown): ApiError {
  if (isApiError(err)) return err
  if (!axios.isAxiosError(err)) return unexpected(null, err)

  const response = err.response
  if (!response) {
    return new ApiError({ kind: 'network', status: null, message: MESSAGES.network })
  }

  const { status, data } = response
  switch (status) {
    case 400: {
      const nonFieldErrors = nonFieldErrorsOf(data)
      return new ApiError({
        kind: 'validation',
        status,
        message: nonFieldErrors[0] ?? MESSAGES.validation,
        fieldErrors: flattenFieldErrors(data),
        nonFieldErrors,
      })
    }
    case 401:
      return new ApiError({ kind: 'unauthenticated', status, message: MESSAGES.unauthenticated })
    case 403:
      return new ApiError({ kind: 'forbidden', status, message: MESSAGES.forbidden })
    case 404:
      return new ApiError({ kind: 'not_found', status, message: MESSAGES.not_found })
    case 409: {
      const detail = isRecord(data) && typeof data.detail === 'string' ? data.detail : null
      return new ApiError({
        kind: 'conflict',
        status,
        message: detail ?? MESSAGES.conflict,
        nonFieldErrors: detail ? [detail] : [],
      })
    }
    case 429:
      return new ApiError({
        kind: 'rate_limited',
        status,
        message: retryAfterMessage(response.headers?.['retry-after']),
      })
    default:
      return unexpected(status, err)
  }
}
