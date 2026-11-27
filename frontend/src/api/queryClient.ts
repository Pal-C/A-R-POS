import { QueryClient } from '@tanstack/react-query'
import { isApiError } from './errors'

/** Client errors (4xx) are deterministic; retrying them only delays the error state. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.status !== null && error.status >= 400 && error.status < 500) {
    return false
  }
  return failureCount < 1
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 30_000,
        // Counter machines switch windows constantly; avoid a refetch storm on every focus.
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  })
}
