import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { ApiError, MESSAGES, flattenFieldErrors, isApiError, toApiError } from './errors'

function httpError(status: number, data: unknown, headers: Record<string, string> = {}): AxiosError {
  const config = { headers: new AxiosHeaders() }
  const response = {
    status,
    statusText: '',
    data,
    headers: new AxiosHeaders(headers),
    config,
  } as AxiosResponse
  return new AxiosError('Request failed', 'ERR_BAD_RESPONSE', config, {}, response)
}

describe('toApiError', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('maps a missing response to a network error', () => {
    const err = toApiError(new AxiosError('Network Error', 'ERR_NETWORK', { headers: new AxiosHeaders() }, {}))
    expect(err.kind).toBe('network')
    expect(err.status).toBeNull()
    expect(err.message).toBe(MESSAGES.network)
  })

  it('maps a timeout to a network error', () => {
    const err = toApiError(new AxiosError('timeout', 'ECONNABORTED', { headers: new AxiosHeaders() }, {}))
    expect(err.kind).toBe('network')
  })

  it('maps 400 field errors and keeps non-field errors', () => {
    const err = toApiError(
      httpError(400, { quantity: ['Must be positive.'], non_field_errors: ['Customer is archived.'] }),
    )
    expect(err.kind).toBe('validation')
    expect(err.status).toBe(400)
    expect(err.fieldErrors).toEqual({ quantity: ['Must be positive.'] })
    expect(err.nonFieldErrors).toEqual(['Customer is archived.'])
    expect(err.message).toBe('Customer is archived.')
  })

  it('uses the generic validation message when only field errors exist', () => {
    const err = toApiError(httpError(400, { username: ['This field is required.'] }))
    expect(err.message).toBe(MESSAGES.validation)
  })

  it('treats a 400 detail string as a non-field error', () => {
    const err = toApiError(httpError(400, { detail: 'Sale is already finalized.' }))
    expect(err.nonFieldErrors).toEqual(['Sale is already finalized.'])
    expect(err.message).toBe('Sale is already finalized.')
  })

  it('treats a 400 list of strings as non-field errors', () => {
    const err = toApiError(httpError(400, ['Bad request.']))
    expect(err.nonFieldErrors).toEqual(['Bad request.'])
  })

  it.each([
    [401, 'unauthenticated', MESSAGES.unauthenticated],
    [403, 'forbidden', MESSAGES.forbidden],
    [404, 'not_found', MESSAGES.not_found],
  ] as const)('maps %i to %s', (status, kind, message) => {
    const err = toApiError(httpError(status, { detail: 'server text' }))
    expect(err.kind).toBe(kind)
    expect(err.message).toBe(message)
  })

  it('maps 409 with a string detail to that detail', () => {
    const err = toApiError(httpError(409, { detail: 'Stock changed.' }))
    expect(err.kind).toBe('conflict')
    expect(err.message).toBe('Stock changed.')
  })

  it('keeps the current values sent with a 409', () => {
    const err = toApiError(httpError(409, { detail: 'Changed.', current: { selling_price: '470.00' } }))
    expect(err.current).toEqual({ selling_price: '470.00' })
  })

  it('maps 409 without a string detail to the generic conflict message', () => {
    const err = toApiError(httpError(409, { detail: { code: 'x' } }))
    expect(err.message).toBe(MESSAGES.conflict)
  })

  it('maps 429 using Retry-After', () => {
    const err = toApiError(httpError(429, { detail: 'throttled' }, { 'retry-after': '42' }))
    expect(err.kind).toBe('rate_limited')
    expect(err.message).toBe('Too many attempts. Try again in 42 seconds.')
  })

  it('maps 429 without Retry-After', () => {
    const err = toApiError(httpError(429, {}))
    expect(err.message).toBe('Too many attempts. Try again later.')
  })

  it.each([500, 502, 418])('maps %i to unexpected without leaking details', (status) => {
    const err = toApiError(httpError(status, '<html>Traceback (most recent call last)</html>'))
    expect(err.kind).toBe('unexpected')
    expect(err.message).toBe(MESSAGES.unexpected)
    expect(err.message).not.toContain('Traceback')
    expect(console.error).toHaveBeenCalled()
  })

  it('maps a non-axios value to unexpected', () => {
    const err = toApiError(new TypeError('boom'))
    expect(err.kind).toBe('unexpected')
    expect(err.message).toBe(MESSAGES.unexpected)
  })

  it('returns an existing ApiError unchanged', () => {
    const original = new ApiError({ kind: 'forbidden', status: 403, message: 'x' })
    expect(toApiError(original)).toBe(original)
    expect(isApiError(original)).toBe(true)
    expect(isApiError(new Error('x'))).toBe(false)
  })
})

describe('flattenFieldErrors', () => {
  it('flattens nested DRF errors to dotted keys', () => {
    expect(
      flattenFieldErrors({
        items: [{ quantity: ['Too many.'] }, {}],
        address: { city: ['Required.'] },
        name: 'Single string.',
      }),
    ).toEqual({
      'items.0.quantity': ['Too many.'],
      'address.city': ['Required.'],
      name: ['Single string.'],
    })
  })

  it('ignores non_field_errors and detail at the top level', () => {
    expect(flattenFieldErrors({ non_field_errors: ['x'], detail: 'y', a: ['b'] })).toEqual({ a: ['b'] })
  })
})
