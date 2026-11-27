import type { CurrentUser } from '../api/auth'

/** Session state machine (data-model.md#session-authcontext-state). */
export type SessionStatus = 'checking' | 'authenticated' | 'anonymous' | 'unreachable'
export type EndReason = 'signed_out' | 'expired' | null

export interface AuthState {
  status: SessionStatus
  user: CurrentUser | null
  endReason: EndReason
  /** Display-safe reason the session check failed (status 'unreachable'). */
  checkError: string | null
}

export type AuthAction =
  | { type: 'session_found'; user: CurrentUser }
  | { type: 'no_session' }
  | { type: 'check_failed'; message: string }
  | { type: 'retry' }
  | { type: 'signed_in'; user: CurrentUser }
  | { type: 'signed_out' }
  | { type: 'expired' }

export const initialAuthState: AuthState = { status: 'checking', user: null, endReason: null, checkError: null }

export function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'session_found':
    case 'signed_in':
      return { status: 'authenticated', user: action.user, endReason: null, checkError: null }
    case 'no_session':
      return { status: 'anonymous', user: null, endReason: null, checkError: null }
    case 'check_failed':
      return { status: 'unreachable', user: null, endReason: null, checkError: action.message }
    case 'retry':
      return state.status === 'unreachable' ? initialAuthState : state
    case 'signed_out':
      return { status: 'anonymous', user: null, endReason: 'signed_out', checkError: null }
    case 'expired':
      // Only a live session can expire; repeated 401s after that are ignored.
      return state.status === 'authenticated'
        ? { status: 'anonymous', user: null, endReason: 'expired', checkError: null }
        : state
  }
}
