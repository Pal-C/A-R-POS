import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useReducer, type ReactNode } from 'react'
import { authApi } from '../api/auth'
import { setUnauthenticatedHandler } from '../api/client'
import { MESSAGES, toApiError } from '../api/errors'
import { AuthContext, type AuthContextValue } from './AuthContext'
import { authReducer, initialAuthState } from './authReducer'

function hasCsrfCookie(): boolean {
  return document.cookie.split(';').some((c) => c.trim().startsWith('csrftoken='))
}

/**
 * Holds the staff session for the whole app (research R7). Nothing is persisted in
 * browser storage: the HttpOnly session cookie is the only credential.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState)
  const queryClient = useQueryClient()

  // Session check on load and on retry (status returns to 'checking').
  useEffect(() => {
    if (state.status !== 'checking') return
    let cancelled = false
    Promise.all([authApi.csrf(), authApi.me()])
      .then(([, user]) => {
        if (!cancelled) dispatch({ type: 'session_found', user })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const apiError = toApiError(error)
        if (apiError.kind === 'unauthenticated') dispatch({ type: 'no_session' })
        // Network failures say so; server errors get the generic message (review finding 3).
        else dispatch({ type: 'check_failed', message: apiError.kind === 'network' ? MESSAGES.network : MESSAGES.unexpected })
      })
    return () => {
      cancelled = true
    }
  }, [state.status])

  // Any 401 from a data request means the server session is gone (FR-007).
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      queryClient.clear()
      dispatch({ type: 'expired' })
    })
    return () => setUnauthenticatedHandler(null)
  }, [queryClient])

  // Another tab may have signed out or signed in someone else. That never shows up
  // as a 401 here, so re-confirm who is signed in whenever this tab regains focus.
  const currentUserId = state.user?.id
  useEffect(() => {
    if (state.status !== 'authenticated') return
    let active = true
    let inFlight = false
    const recheck = () => {
      if (inFlight || document.visibilityState === 'hidden') return
      inFlight = true
      authApi
        .me()
        .then((user) => {
          if (!active) return
          if (user.id !== currentUserId) queryClient.clear()
          dispatch({ type: 'session_found', user })
        })
        .catch((error: unknown) => {
          if (!active) return
          if (toApiError(error).kind === 'unauthenticated') {
            queryClient.clear()
            dispatch({ type: 'expired' })
          }
          // Network or server errors: keep the current state; data requests will report them.
        })
        .finally(() => {
          inFlight = false
        })
    }
    window.addEventListener('focus', recheck)
    document.addEventListener('visibilitychange', recheck)
    return () => {
      active = false
      window.removeEventListener('focus', recheck)
      document.removeEventListener('visibilitychange', recheck)
    }
  }, [state.status, currentUserId, queryClient])

  const login = useCallback(
    async (username: string, password: string) => {
      if (!hasCsrfCookie()) await authApi.csrf()
      const user = await authApi.login(username, password)
      queryClient.clear()
      dispatch({ type: 'signed_in', user })
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Sign out locally even when the server can't be reached (spec edge case).
    } finally {
      queryClient.clear()
      dispatch({ type: 'signed_out' })
    }
  }, [queryClient])

  const retry = useCallback(() => dispatch({ type: 'retry' }), [])

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      logout,
      retry,
      hasPermission: (permission: string) =>
        !!state.user && (state.user.is_superuser || state.user.permissions.includes(permission)),
    }),
    [state, login, logout, retry],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
