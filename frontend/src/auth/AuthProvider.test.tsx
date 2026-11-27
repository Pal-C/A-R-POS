import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useState } from 'react'
import { apiGet, apiPost } from '../api/client'
import { isApiError } from '../api/errors'
import type { WorkArea, WorkAreaPageProps } from '../routes/workAreas'
import { workAreas } from '../routes/workAreas'
import { api, asAnonymous, asUser, staffUser, unauthenticated } from '../test/handlers'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

/** A work area whose page fires API requests on demand. */
function ProbePage({ area }: WorkAreaPageProps) {
  const [message, setMessage] = useState('')
  const fire = (count: number) => {
    setMessage('')
    for (let i = 0; i < count; i++) {
      apiGet(`/probe/${i}/`).catch((e: unknown) => setMessage(isApiError(e) ? e.message : 'unknown'))
    }
  }
  return (
    <section>
      <h1>{area.label}</h1>
      <button onClick={() => fire(1)}>Load</button>
      <button onClick={() => fire(3)}>Load three</button>
      <button onClick={() => apiPost('/probe/forbidden/').catch((e: unknown) => setMessage(isApiError(e) ? e.message : ''))}>
        Forbidden action
      </button>
      {message && <p role="alert">{message}</p>}
    </section>
  )
}

const probeArea: WorkArea = { path: '/probe', label: 'Probe', load: async () => ProbePage }
const areas = [...workAreas, probeArea]

describe('AuthProvider session handling', () => {
  it('keeps a valid session across reloads without flashing the sign-in screen', async () => {
    asUser()
    const { currentPath } = renderApp('/customers')

    // A loading state (route chunk or session check) is shown first, never the sign-in form.
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Customers' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    expect(currentPath()).toBe('/customers')
  })

  it('returns to sign-in when the session ends, then back to the same page', async () => {
    asUser()
    const { user, queryClient, currentPath } = renderApp('/probe?tab=2', { areas })
    await screen.findByRole('heading', { name: 'Probe' })
    queryClient.setQueryData(['secret'], 'previous data')

    // The session ends elsewhere (another tab, expiry): every request now gets 401.
    asAnonymous()
    server.use(http.get(api('/probe/:n/'), unauthenticated))
    await user.click(screen.getByRole('button', { name: 'Load' }))

    expect(await screen.findByText('Your session has ended. Please sign in again.')).toBeInTheDocument()
    expect(currentPath()).toBe('/login?next=%2Fprobe%3Ftab%3D2')
    expect(queryClient.getQueryData(['secret'])).toBeUndefined()

    await user.type(screen.getByLabelText('Username'), staffUser.username)
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Probe' })).toBeInTheDocument()
    expect(currentPath()).toBe('/probe?tab=2')
  })

  it('redirects once when several requests fail with 401 together', async () => {
    asUser()
    const meCalls = vi.fn()
    const { user, router } = renderApp('/probe', { areas })
    await screen.findByRole('heading', { name: 'Probe' })
    const navigations: string[] = []
    router.subscribe((state) => navigations.push(state.location.pathname))

    server.use(
      http.get(api('/probe/:n/'), unauthenticated),
      http.get(api('/auth/me/'), () => {
        meCalls()
        return unauthenticated()
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Load three' }))

    await screen.findByText('Your session has ended. Please sign in again.')
    expect(navigations.filter((path) => path === '/login')).toHaveLength(1)
  })

  it('does not sign out on a permission error', async () => {
    asUser()
    server.use(http.post(api('/probe/forbidden/'), () => HttpResponse.json({ detail: 'x' }, { status: 403 })))
    const { user } = renderApp('/probe', { areas })

    await user.click(await screen.findByRole('button', { name: 'Forbidden action' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("You don't have permission to do that.")
    expect(screen.getByTestId('current-user')).toHaveTextContent(staffUser.display_name)
  })

  it('shows a generic error, not "cannot reach the server", when the session check hits a server error', async () => {
    server.use(http.get(api('/auth/me/'), () => HttpResponse.json({ detail: 'boom' }, { status: 500 })))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp('/sales')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Something went wrong. Please try again.')
    expect(alert).not.toHaveTextContent('Cannot reach the server')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  it('switches to the new staff member when another tab signed in someone else', async () => {
    asUser()
    const { queryClient } = renderApp('/sales')
    await screen.findByRole('heading', { name: 'Sales' })
    queryClient.setQueryData(['secret'], 'previous staff data')

    asUser({ ...staffUser, id: 2, username: 'juan', display_name: 'Juan Cruz' })
    act(() => {
      fireEvent.focus(window)
    })

    await waitFor(() => expect(screen.getByTestId('current-user')).toHaveTextContent('Juan Cruz'))
    expect(queryClient.getQueryData(['secret'])).toBeUndefined()
  })

  it('keeps the cache when the same staff member is still signed in on focus', async () => {
    asUser()
    const { queryClient } = renderApp('/sales')
    await screen.findByRole('heading', { name: 'Sales' })
    queryClient.setQueryData(['kept'], 'data')

    act(() => {
      fireEvent.focus(window)
    })

    await waitFor(() => expect(screen.getByTestId('current-user')).toHaveTextContent(staffUser.display_name))
    expect(queryClient.getQueryData(['kept'])).toBe('data')
  })

  it('shows sign-in when another tab signed out and this tab regains focus', async () => {
    asUser()
    renderApp('/sales')
    await screen.findByRole('heading', { name: 'Sales' })

    asAnonymous()
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(await screen.findByText('Your session has ended. Please sign in again.')).toBeInTheDocument()
  })

  it('shows the unreachable state when offline on load and recovers on retry', async () => {
    server.use(
      http.get(api('/auth/me/'), () => HttpResponse.error()),
      http.get(api('/auth/csrf/'), () => HttpResponse.error()),
    )
    const { user } = renderApp('/sales')

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server')
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()

    asUser()
    server.use(http.get(api('/auth/csrf/'), () => new HttpResponse(null, { status: 204 })))
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Sales' })).toBeInTheDocument())
  })
})
