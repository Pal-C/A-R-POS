import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeSale } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const canceller = { ...staffUser, display_name: 'Maria Reyes', permissions: ['sales.cancel_sale'] }
const sale = makeSale({ id: 142 })

describe('Cancel Sale', () => {
  it('requires a reason and confirmation, then cancels and returns to the sale', async () => {
    asUser(canceller)
    let body: unknown
    server.use(
      http.get(api('/sales/142/'), () => HttpResponse.json(sale)),
      http.post(api('/sales/142/cancel/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...sale, status: 'CANCELLED', refund_due: '650.00' })
      }),
    )
    const { user, currentPath } = renderApp('/sales/142/cancel')

    expect(await screen.findByRole('heading', { level: 1, name: 'Cancel Sale' })).toBeInTheDocument()
    const summary = await screen.findByText('Sale #S20261127-000142')
    expect(summary.closest('.ar-summary')).toHaveTextContent('Juan Dela Cruz | 3 items | Cash | 11/27/2026')
    expect(summary.closest('.ar-summary')).toHaveTextContent('₱650.00')
    expect(screen.getByRole('note')).toHaveTextContent('Items are returned to stock. Recorded as cancelled by Maria Reyes')

    const confirm = screen.getByRole('button', { name: 'Confirm cancellation' })
    expect(confirm).toBeDisabled()
    await user.type(screen.getByLabelText(/Reason for cancellation/), 'Customer returned the items')
    expect(confirm).toBeDisabled()
    await user.click(screen.getByLabelText('I understand this reverses the payment record'))
    await user.click(confirm)

    expect(await screen.findByText('Sale S20261127-000142 cancelled. Refund due ₱650.00.')).toBeInTheDocument()
    expect(body).toEqual({ reason: 'Customer returned the items' })
    await waitFor(() => expect(currentPath()).toBe('/sales/142'))
  })

  it('denies access without the cancel permission', async () => {
    asUser()
    server.use(http.get(api('/sales/142/'), () => HttpResponse.json(sale)))
    renderApp('/sales/142/cancel')
    expect(await screen.findByRole('heading', { name: "You don't have access to this area" })).toBeInTheDocument()
  })

  it('explains when a sale cannot be cancelled', async () => {
    asUser(canceller)
    server.use(http.get(api('/sales/142/'), () => HttpResponse.json({ ...sale, status: 'CANCELLED' })))
    renderApp('/sales/142/cancel')
    expect(await screen.findByText(/can't be cancelled because it is already cancelled/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm cancellation' })).not.toBeInTheDocument()
  })

  it('links to cancellation from the sale for permitted staff', async () => {
    asUser(canceller)
    server.use(http.get(api('/sales/142/'), () => HttpResponse.json(sale)))
    const { user } = renderApp('/sales/142')
    await user.click(await screen.findByRole('link', { name: /cancel sale/i }))
    expect(await within(document.body).findByRole('heading', { level: 1, name: 'Cancel Sale' })).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    asUser(canceller)
    server.use(http.get(api('/sales/142/'), () => HttpResponse.json(sale)))
    const { container } = renderApp('/sales/142/cancel')
    await screen.findByText('Sale #S20261127-000142')
    await expectNoAxeViolations(container)
  })
})
