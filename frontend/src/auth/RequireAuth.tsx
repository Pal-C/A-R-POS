import { Navigate, Outlet, useLocation } from 'react-router'
import { ServerUnreachablePage } from '../pages/ServerUnreachablePage'
import { SessionCheckingPage } from '../pages/SessionCheckingPage'
import { useAuth } from './useAuth'

/** Layout route guarding everything below it (FR-010). */
export function RequireAuth() {
  const { status, endReason } = useAuth()
  const location = useLocation()

  if (status === 'checking') return <SessionCheckingPage />
  if (status === 'unreachable') return <ServerUnreachablePage />
  if (status === 'anonymous') {
    // After an explicit sign-out the next person starts fresh at Home.
    if (endReason === 'signed_out') return <Navigate to="/login" replace />
    const next = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return <Outlet />
}
