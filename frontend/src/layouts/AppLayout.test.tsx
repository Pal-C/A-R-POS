import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setConnectionStatus } from '../lib/connection'
import { expectNoAxeViolations } from '../test/axe'
import { api, asUser, staffUser } from '../test/handlers'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

afterEach(() => setConnectionStatus('online'))

async function openUserMenu(user: ReturnType<typeof renderApp>['user']) {
  await user.click(await screen.findByRole('button', { name: /Maria Santos/ }))
}

describe('AppLayout shell', () => {
  it('lists the areas in the reference order without POS or Analytics', async () => {
    asUser()
    renderApp('/')
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    const labels = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent)
    expect(labels).toEqual(['Home', 'Sales', 'Inventory', 'Services', 'Customers', 'Pre-Orders'])
    expect(within(nav).queryByText('POS')).not.toBeInTheDocument()
    expect(within(nav).queryByText('Analytics')).not.toBeInTheDocument()
  })

  it('marks the active area and shows its title and subtitle', async () => {
    asUser()
    renderApp('/stringing')
    expect(await screen.findByRole('heading', { level: 1, name: 'Stringing Orders' })).toBeInTheDocument()
    expect(screen.getByText('Track, update and search racket stringing orders')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Services' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows the user badge with initials, name and role', async () => {
    asUser()
    renderApp('/')
    const badge = await screen.findByRole('button', { name: /Maria Santos/ })
    expect(badge).toHaveTextContent('MS')
    expect(badge).toHaveTextContent('Staff')
  })

  it('labels superusers as Admin', async () => {
    asUser({ ...staffUser, is_superuser: true })
    renderApp('/')
    expect(await screen.findByRole('button', { name: /Maria Santos/ })).toHaveTextContent('Admin')
  })

  it('signs out from the user menu, clears cached data and shows the sign-in screen', async () => {
    asUser()
    const logoutCalls = vi.fn()
    server.use(
      http.post(api('/auth/logout/'), () => {
        logoutCalls()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user, queryClient, currentPath } = renderApp('/sales')
    await screen.findByRole('heading', { level: 1, name: 'Sales' })
    queryClient.setQueryData(['customers', 'list'], { secret: 'previous staff data' })

    await openUserMenu(user)
    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByText('You have been signed out.')).toBeInTheDocument()
    expect(logoutCalls).toHaveBeenCalledTimes(1)
    expect(queryClient.getQueryData(['customers', 'list'])).toBeUndefined()
    expect(currentPath()).toBe('/login')
  })

  it('still signs out locally when the server cannot be reached', async () => {
    asUser()
    server.use(http.post(api('/auth/logout/'), () => HttpResponse.error()))
    const { user } = renderApp('/')

    await openUserMenu(user)
    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByText('You have been signed out.')).toBeInTheDocument()
    expect(screen.queryByTestId('current-user')).not.toBeInTheDocument()
  })

  it('shows Synced, then Offline after a network failure, then Synced again', async () => {
    asUser()
    const { user } = renderApp('/sales')
    await waitFor(() => expect(screen.getByText('Synced')).toBeInTheDocument())

    server.use(http.get(api('/customers/'), () => HttpResponse.error()))
    await user.click(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Customers' }))
    await waitFor(() => expect(screen.getByText('Offline')).toBeInTheDocument())

    await user.click(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Pre-Orders' }))
    await waitFor(() => expect(screen.getByText('Synced')).toBeInTheDocument())
  })

  it('offers a skip link first that moves focus to the main content', async () => {
    asUser()
    const { user } = renderApp('/')
    await screen.findByRole('heading', { level: 1, name: 'Home' })

    await user.tab()
    const skip = screen.getByRole('link', { name: 'Skip to content' })
    expect(skip).toHaveFocus()
    await user.click(skip)
    expect(screen.getByRole('main')).toHaveFocus()
  })

  it('keeps accessible names on every nav link for the collapsed sidebar', async () => {
    asUser()
    renderApp('/')
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    for (const link of within(nav).getAllByRole('link')) {
      expect(link).toHaveAttribute('title', link.textContent)
    }
  })

  it('has no accessibility violations', async () => {
    asUser()
    const { container } = renderApp('/sales')
    await screen.findByRole('heading', { level: 1, name: 'Sales' })
    await expectNoAxeViolations(container)
  })
})
