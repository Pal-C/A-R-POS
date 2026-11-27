import type { ReactNode } from 'react'
import { MESSAGES, isApiError } from '../api/errors'

interface QueryStateProps {
  isPending: boolean
  error: unknown
  /** True when the request succeeded but there is nothing to show. */
  isEmpty?: boolean
  emptyText?: string
  loadingText?: string
  children: ReactNode
}

/**
 * Shared loading / empty / error / success rendering for data-driven views
 * (constitution Principle III). Errors show only the normalized, display-safe message.
 */
export function QueryState({
  isPending,
  error,
  isEmpty = false,
  emptyText = 'Nothing here yet.',
  loadingText = 'Loading…',
  children,
}: QueryStateProps) {
  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        {isApiError(error) ? error.message : MESSAGES.unexpected}
      </div>
    )
  }
  if (isPending) {
    return (
      <div role="status" aria-live="polite">
        <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
        {loadingText}
      </div>
    )
  }
  if (isEmpty) return <p className="text-body-secondary">{emptyText}</p>
  return <>{children}</>
}
