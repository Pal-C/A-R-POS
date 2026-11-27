import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { api, asUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

describe('WorkAreaPlaceholder record count', () => {
  it('shows the number of records', async () => {
    asUser()
    server.use(http.get(api('/preorders/'), () => HttpResponse.json({ count: 3, next: null, previous: null, results: [] })))
    renderApp('/preorders')

    expect(await screen.findByText('3 pre-orders')).toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    asUser()
    renderApp('/customers')

    expect(await screen.findByText('No customers yet.')).toBeInTheDocument()
  })

  it('shows a readable alert when the server cannot be reached', async () => {
    asUser()
    server.use(http.get(api('/sales/'), () => HttpResponse.error()))
    renderApp('/sales')

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server')
  })
})
