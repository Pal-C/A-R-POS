import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { api, asAnonymous, asUser, staffUser } from '../test/handlers'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

describe('LoginPage', () => {
  it('sends signed-out visitors to sign-in and back to the requested page afterwards', async () => {
    asAnonymous()
    const { user, currentPath } = renderApp('/preorders')

    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    expect(currentPath()).toBe('/login?next=%2Fpreorders')

    await user.type(screen.getByLabelText('Username'), 'maria')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Pre-orders' })).toBeInTheDocument()
    expect(currentPath()).toBe('/preorders')
    expect(screen.getByTestId('current-user')).toHaveTextContent(staffUser.display_name)
  })

  it('shows one generic message for wrong credentials and clears the password', async () => {
    asAnonymous()
    const { user } = renderApp('/login')

    await user.type(await screen.findByLabelText('Username'), 'maria')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
    expect(screen.getByLabelText('Password')).toHaveValue('')
    expect(screen.getByLabelText('Username')).toHaveValue('maria')
  })

  it('does not send the form when fields are empty and flags them', async () => {
    asAnonymous()
    const loginCalls = vi.fn()
    server.use(
      http.post(api('/auth/login/'), () => {
        loginCalls()
        return HttpResponse.json({}, { status: 400 })
      }),
    )
    const { user } = renderApp('/login')

    await user.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(screen.getByLabelText('Username')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Enter your username.')).toBeInTheDocument()
    expect(loginCalls).not.toHaveBeenCalled()
  })

  it('disables submit while pending and sends a single request on double click', async () => {
    asAnonymous()
    const loginCalls = vi.fn()
    let release: () => void = () => {}
    server.use(
      http.post(api('/auth/login/'), async () => {
        loginCalls()
        await new Promise<void>((resolve) => {
          release = resolve
        })
        return HttpResponse.json(staffUser)
      }),
    )
    const { user } = renderApp('/login')

    await user.type(await screen.findByLabelText('Username'), 'maria')
    await user.type(screen.getByLabelText('Password'), 'secret')
    const submit = screen.getByRole('button', { name: 'Sign in' })
    await user.dblClick(submit)

    expect(await screen.findByRole('button', { name: /signing in/i })).toBeDisabled()
    await waitFor(() => expect(loginCalls).toHaveBeenCalledTimes(1))
    release()
    expect(await screen.findByRole('heading', { name: /welcome/i })).toBeInTheDocument()
    expect(loginCalls).toHaveBeenCalledTimes(1)
  })

  it('shows the rate-limit message when throttled', async () => {
    asAnonymous()
    server.use(
      http.post(api('/auth/login/'), () =>
        HttpResponse.json({ detail: 'throttled' }, { status: 429, headers: { 'Retry-After': '30' } }),
      ),
    )
    const { user } = renderApp('/login')

    await user.type(await screen.findByLabelText('Username'), 'maria')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Try again in 30 seconds.')
  })

  it('sends signed-in staff visiting /login to Home', async () => {
    asUser()
    const { currentPath } = renderApp('/login')

    expect(await screen.findByRole('heading', { name: `Welcome, ${staffUser.display_name}` })).toBeInTheDocument()
    expect(currentPath()).toBe('/')
  })

  it('ignores an external next target after sign-in', async () => {
    asAnonymous()
    const { user, currentPath } = renderApp('/login?next=%2F%2Fevil.com')

    await user.type(await screen.findByLabelText('Username'), 'maria')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: /welcome/i })).toBeInTheDocument()
    expect(currentPath()).toBe('/')
  })
})
