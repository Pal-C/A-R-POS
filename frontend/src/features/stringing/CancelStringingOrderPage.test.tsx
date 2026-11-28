import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeStringingOrder, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const canceller = { ...staffUser, permissions: ['stringing.cancel_stringingorder'] }
const order = makeStringingOrder({ status: 'IN_PROGRESS', status_display: 'In Progress', amount_paid: '270.00', balance: '80.00' })

function serveOrder(value = order) {
  server.use(
    http.get(api('/stringing/orders/126/'), () => HttpResponse.json(value)),
    http.get(api('/stringing/orders/126/payments/'), () => HttpResponse.json(page([]))),
    http.get(api('/stringing/orders/'), () => HttpResponse.json(page([value]))),
    http.get(api('/stringing/orders/status-counts/'), () => HttpResponse.json({ all: 1, RECEIVED: 0, IN_PROGRESS: 1, READY: 0, COMPLETED: 0, CANCELLED: 0 })),
  )
}

describe('Cancel Stringing Order', () => {
  it('requires a reason and confirmation, sends the materials choice and shows the refund due', async () => {
    asUser(canceller)
    serveOrder()
    let body: unknown
    server.use(
      http.post(api('/stringing/orders/126/cancel/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...order, status: 'CANCELLED', status_display: 'Cancelled', refund_due: '270.00', balance: '0.00', materials_used: true })
      }),
    )
    const { user, currentPath } = renderApp('/stringing/126/cancel')
    expect(await screen.findByRole('heading', { level: 1, name: 'Cancel Stringing Order' })).toBeInTheDocument()
    const summary = (await screen.findByText('Order STR-2026-000126')).closest('.ar-summary')!
    expect(summary).toHaveTextContent('Juan Dela Cruz | Arcsaber 11 | BG80 @ 27 lbs | 11/19/2026')
    expect(summary).toHaveTextContent('Paid ₱270.00')
    expect(within(summary as HTMLElement).getByText('In Progress')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('saved to the audit log. The order is never erased.')
    expect(screen.getByLabelText(/No materials used yet/)).toBeChecked()

    const confirm = screen.getByRole('button', { name: 'Confirm cancellation' })
    expect(confirm).toBeDisabled()
    await user.type(screen.getByLabelText(/Reason for cancellation/), 'Customer changed mind')
    await user.click(screen.getByLabelText(/Materials already used/))
    expect(confirm).toBeDisabled()
    await user.click(screen.getByLabelText('I understand this order will be marked Cancelled'))
    await user.click(confirm)

    expect(await screen.findByText('Order STR-2026-000126 cancelled. Refund due ₱270.00.')).toBeInTheDocument()
    expect(body).toEqual({ reason: 'Customer changed mind', materials_used: true })
    await waitFor(() => expect(currentPath()).toBe('/stringing?order=126'))
  })

  it('explains when the order became final meanwhile', async () => {
    asUser(canceller)
    let current = order
    server.use(
      http.get(api('/stringing/orders/126/'), () => HttpResponse.json(current)),
      http.post(api('/stringing/orders/126/cancel/'), () => {
        current = { ...order, status: 'COMPLETED', status_display: 'Completed' }
        return HttpResponse.json(['Completed orders cannot be cancelled.'], { status: 400 })
      }),
    )
    const { user } = renderApp('/stringing/126/cancel')
    await user.type(await screen.findByLabelText(/Reason for cancellation/), 'x')
    await user.click(screen.getByLabelText('I understand this order will be marked Cancelled'))
    await user.click(screen.getByRole('button', { name: 'Confirm cancellation' }))
    expect(await screen.findByText(/can't be cancelled because it is already Completed/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to the order' })).toHaveAttribute('href', '/stringing?order=126')
  })

  it('goes back to the list when opened directly', async () => {
    asUser(canceller)
    serveOrder()
    const { user, currentPath } = renderApp('/stringing/126/cancel')
    await user.click(await screen.findByRole('button', { name: 'Back' }))
    await waitFor(() => expect(currentPath()).toBe('/stringing'))
  })

  it('denies access without the cancel permission', async () => {
    asUser()
    serveOrder()
    renderApp('/stringing/126/cancel')
    expect(await screen.findByRole('heading', { name: "You don't have access to this area" })).toBeInTheDocument()
  })

  it('links to cancellation from Details for permitted staff', async () => {
    asUser(canceller)
    serveOrder()
    const { user } = renderApp('/stringing?order=126')
    const dialog = await screen.findByRole('dialog', { name: 'Order STR-2026-000126' })
    await user.click(within(dialog).getByRole('link', { name: 'Cancel order' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Cancel Stringing Order' })).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    asUser(canceller)
    serveOrder()
    const { container } = renderApp('/stringing/126/cancel')
    await screen.findByText('Order STR-2026-000126')
    await expectNoAxeViolations(container)
  })
})
