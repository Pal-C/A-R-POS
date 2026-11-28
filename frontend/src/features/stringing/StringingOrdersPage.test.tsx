import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeStringingOrder, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const manager = { ...staffUser, permissions: ['stringing.cancel_stringingorder'] }
const counts = { all: 28, RECEIVED: 5, IN_PROGRESS: 6, READY: 3, COMPLETED: 13, CANCELLED: 1 }

const orders = [
  makeStringingOrder({ id: 128, customer: null, string_type: 'BG66 Ultimax', tension: '26 lbs', balance: '250.00' }),
  makeStringingOrder({ id: 125, status: 'READY', status_display: 'Ready for Pickup', racket_description: 'Duora 10', string_type: 'Nano 7', tension: '' }),
  makeStringingOrder({ id: 124, status: 'COMPLETED', status_display: 'Completed', balance: '0.00' }),
  makeStringingOrder({ id: 122, status: 'CANCELLED', status_display: 'Cancelled', balance: '0.00', refund_due: '270.00' }),
]

function serve({ results = orders, count = 28 } = {}) {
  const listRequests: URLSearchParams[] = []
  const countRequests: URLSearchParams[] = []
  server.use(
    http.get(api('/stringing/orders/'), ({ request }) => {
      listRequests.push(new URL(request.url).searchParams)
      return HttpResponse.json(page(results, count))
    }),
    http.get(api('/stringing/orders/status-counts/'), ({ request }) => {
      countRequests.push(new URL(request.url).searchParams)
      return HttpResponse.json(counts)
    }),
  )
  return { listRequests, countRequests }
}

describe('Stringing Orders list', () => {
  it('shows orders with the reference columns and status chips with counts', async () => {
    asUser(manager)
    serve()
    renderApp('/stringing')
    expect(await screen.findByRole('heading', { level: 1, name: 'Stringing Orders' })).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Stringing orders' })
    const first = (await within(table).findByRole('button', { name: 'STR-2026-000128' })).closest('tr')!
    expect(first).toHaveTextContent('Walk-in')
    expect(first).toHaveTextContent('BG66 Ultimax @ 26 lbs')
    expect(first).toHaveTextContent('11/19/2026')
    expect(first).toHaveTextContent('₱250.00')
    expect(within(first).getByText('Received')).toHaveClass('ar-badge--outline')
    const ready = within(table).getByRole('button', { name: 'STR-2026-000125' }).closest('tr')!
    expect(ready).toHaveTextContent('Nano 7')
    expect(ready).not.toHaveTextContent('@')
    expect(within(ready).getByText('Ready for Pickup')).toHaveClass('ar-badge--yellow')
    expect(within(table).getByText('₱270.00 refund')).toBeInTheDocument()

    const chips = screen.getByRole('group', { name: 'Filter by status' })
    expect(within(chips).getByRole('button', { name: 'All 28' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(chips).getByRole('button', { name: 'In Progress 6' })).toBeInTheDocument()
    expect(screen.getByText(/1–4 of 28 orders|1-4 of 28 orders|Showing/)).toBeInTheDocument()
  })

  it('filters by chip and search, keeping both in the address', async () => {
    asUser(manager)
    const { listRequests, countRequests } = serve()
    const { user, currentPath } = renderApp('/stringing')
    await user.click(await screen.findByRole('button', { name: 'Ready for Pickup 3' }))
    await waitFor(() => expect(currentPath()).toBe('/stringing?status=READY'))
    await user.type(screen.getByRole('searchbox'), 'Mika')
    await waitFor(() => expect(currentPath()).toBe('/stringing?status=READY&search=Mika'))
    await waitFor(() => expect(listRequests.at(-1)?.get('search')).toBe('Mika'))
    expect(listRequests.at(-1)?.get('status')).toBe('READY')
    expect(countRequests.at(-1)?.get('search')).toBe('Mika')
    expect(countRequests.at(-1)?.has('status')).toBe(false)
  })

  it('restores filters from the address and filters by payment and date', async () => {
    asUser(manager)
    const { listRequests } = serve()
    const { user, currentPath } = renderApp('/stringing?payment_state=UNPAID')
    await waitFor(() => expect(listRequests.at(-1)?.get('payment_state')).toBe('UNPAID'))
    await user.click(screen.getByRole('button', { name: /Filter/ }))
    await user.type(screen.getByLabelText('Received from'), '2026-11-01')
    await waitFor(() => expect(currentPath()).toContain('received_from=2026-11-01'))
  })

  it('offers cancel only for open orders and permitted staff', async () => {
    asUser(manager)
    serve()
    const { user, currentPath } = renderApp('/stringing')
    expect(await screen.findByRole('button', { name: 'Cancel order STR-2026-000128' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel order STR-2026-000124' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel order STR-2026-000122' })).not.toBeInTheDocument()
    server.use(http.get(api('/stringing/orders/128/'), () => HttpResponse.json(orders[0])))
    await user.click(screen.getByRole('button', { name: 'Cancel order STR-2026-000128' }))
    await waitFor(() => expect(currentPath()).toBe('/stringing/128/cancel'))
  })

  it('hides cancel without the permission', async () => {
    asUser()
    serve()
    renderApp('/stringing')
    await screen.findByRole('button', { name: 'Open order STR-2026-000128' })
    expect(screen.queryByRole('button', { name: /Cancel order/ })).not.toBeInTheDocument()
  })

  it('shows the right empty states', async () => {
    asUser(manager)
    serve({ results: [], count: 0 })
    const { user, currentPath } = renderApp('/stringing?search=zzz')
    await user.click(await screen.findByRole('button', { name: 'Clear filters' }))
    await waitFor(() => expect(currentPath()).toBe('/stringing'))
    expect(await screen.findByText('No stringing orders yet.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'New order' }).length).toBeGreaterThan(0)
  })

  it('has no accessibility violations', async () => {
    asUser(manager)
    serve()
    const { container } = renderApp('/stringing')
    await screen.findByRole('button', { name: 'Open order STR-2026-000128' })
    await expectNoAxeViolations(container)
  })
})
