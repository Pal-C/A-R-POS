import { createContext } from 'react'
import type { CurrentUser } from '../api/auth'
import type { EndReason, SessionStatus } from './authReducer'

export interface AuthContextValue {
  status: SessionStatus
  user: CurrentUser | null
  endReason: EndReason
  /** Why the session check failed, when status is 'unreachable'. */
  checkError: string | null
  /** Rejects with `ApiError` on failure. */
  login(username: string, password: string): Promise<void>
  /** Never rejects: local state is cleared even if the server can't be reached. */
  logout(): Promise<void>
  /** Re-runs the session check after the server was unreachable. */
  retry(): void
  hasPermission(permission: string): boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)
