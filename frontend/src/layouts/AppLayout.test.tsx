import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { api, asUser, staffUser } from '../test/handlers'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

describe('AppLayout', () => {
  it('shows the signed-in staff member and a sign-out action', async () => {
    asUser()
    renderApp('/')

    expect(await screen.findByTestId('current-user')).toHaveTextContent(staffUser.display_name)
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('signs out on the server, clears cached data and shows the sign-in screen', async () => {
    asUser()
    const logoutCalls = vi.fn()
    server.use(
      http.post(api('/auth/logout/'), () => {
        logoutCalls()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user, queryClient, currentPath } = renderApp('/sales')
    await screen.findByRole('heading', { name: 'Sales' })
    queryClient.setQueryData(['customers', 'list'], { secret: 'previous staff data' })

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

    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByText('You have been signed out.')).toBeInTheDocument()
    expect(screen.queryByTestId('current-user')).not.toBeInTheDocument()
  })
})
