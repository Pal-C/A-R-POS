import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { createQueryClient } from '../api/queryClient'
import { AuthProvider } from '../auth/AuthProvider'
import { appRoutes } from '../routes/router'
import { workAreas, type WorkArea } from '../routes/workAreas'
import { ToastProvider } from '../components/ui/Toast'

/** Renders the full app (providers + routes) at `url` with a fresh cache. */
export function renderApp(url = '/', { areas = workAreas }: { areas?: WorkArea[] } = {}) {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { ...queryClient.getDefaultOptions().queries, retry: false } })
  const router = createMemoryRouter(appRoutes(areas), { initialEntries: [url] })
  const user = userEvent.setup()
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
  const currentPath = () => `${router.state.location.pathname}${router.state.location.search}`
  return { ...utils, router, queryClient, user, currentPath }
}
