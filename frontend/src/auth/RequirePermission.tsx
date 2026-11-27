import type { ReactNode } from 'react'
import { AccessDeniedPage } from '../pages/AccessDeniedPage'
import { useAuth } from './useAuth'

/** UI-level guard only; the server enforces permissions on every request. */
export function RequirePermission({ permission, children }: { permission?: string; children: ReactNode }) {
  const { hasPermission } = useAuth()
  if (permission && !hasPermission(permission)) return <AccessDeniedPage />
  return <>{children}</>
}
