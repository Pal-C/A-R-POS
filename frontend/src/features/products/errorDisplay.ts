import type { ApiError, FieldErrors } from '../../api/errors'

/**
 * Splits a server error into messages shown next to known form fields and an alert
 * for everything else, so no error is ever dropped silently.
 */
export function splitApiError(
  error: ApiError,
  knownFields: Iterable<string>,
  rename: Record<string, string> = {},
): { fieldErrors: FieldErrors; alert: string | null } {
  const known = new Set(knownFields)
  const fieldErrors: FieldErrors = {}
  const other = [...error.nonFieldErrors]
  for (const [key, messages] of Object.entries(error.fieldErrors)) {
    const field = rename[key] ?? key
    if (known.has(field)) fieldErrors[field] = [...(fieldErrors[field] ?? []), ...messages]
    else other.push(...messages)
  }
  const alert = other.length > 0 ? other.join(' ') : Object.keys(fieldErrors).length > 0 ? null : error.message
  return { fieldErrors, alert }
}
