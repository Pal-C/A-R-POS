import type { CurrentUser } from '../api/auth'
import { authReducer, initialAuthState, type AuthState } from './authReducer'

const user: CurrentUser = {
  id: 1,
  username: 'maria',
  first_name: '',
  last_name: '',
  display_name: 'maria',
  is_superuser: false,
  permissions: [],
}
const authenticated: AuthState = { status: 'authenticated', user, endReason: null, checkError: null }
const anonymous: AuthState = { status: 'anonymous', user: null, endReason: null, checkError: null }
const unreachable: AuthState = { status: 'unreachable', user: null, endReason: null, checkError: 'Cannot reach the server.' }

describe('authReducer', () => {
  it('starts in checking', () => {
    expect(initialAuthState).toEqual({ status: 'checking', user: null, endReason: null, checkError: null })
  })

  it('checking -> authenticated when a session is found', () => {
    expect(authReducer(initialAuthState, { type: 'session_found', user })).toEqual(authenticated)
  })

  it('checking -> anonymous when there is no session', () => {
    expect(authReducer(initialAuthState, { type: 'no_session' })).toEqual(anonymous)
  })

  it('checking -> unreachable when the check fails, keeping the message; retry goes back to checking', () => {
    const state = authReducer(initialAuthState, { type: 'check_failed', message: 'Cannot reach the server.' })
    expect(state).toEqual(unreachable)
    expect(authReducer(state, { type: 'retry' })).toEqual(initialAuthState)
  })

  it('a session found while signed in replaces the user (another tab signed in someone else)', () => {
    const other = { ...user, id: 2, username: 'juan', display_name: 'juan' }
    expect(authReducer(authenticated, { type: 'session_found', user: other })).toEqual({ ...authenticated, user: other })
  })

  it('retry is ignored unless unreachable', () => {
    expect(authReducer(authenticated, { type: 'retry' })).toBe(authenticated)
  })

  it('anonymous -> authenticated on sign-in, clearing the end reason', () => {
    const expired: AuthState = { ...anonymous, endReason: 'expired' }
    expect(authReducer(expired, { type: 'signed_in', user })).toEqual(authenticated)
  })

  it('authenticated -> anonymous(signed_out) on sign-out', () => {
    expect(authReducer(authenticated, { type: 'signed_out' })).toEqual({ ...anonymous, endReason: 'signed_out' })
  })

  it('authenticated -> anonymous(expired) on a 401', () => {
    expect(authReducer(authenticated, { type: 'expired' })).toEqual({ ...anonymous, endReason: 'expired' })
  })

  it('expired is ignored when not authenticated', () => {
    const signedOut: AuthState = { ...anonymous, endReason: 'signed_out' }
    expect(authReducer(signedOut, { type: 'expired' })).toBe(signedOut)
    expect(authReducer(initialAuthState, { type: 'expired' })).toBe(initialAuthState)
  })
})
