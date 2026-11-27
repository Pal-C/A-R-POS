import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeProductDetail, makeSale, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const collector = { ...staffUser, permissions: ['sales.record_payment', 'sales.cancel_sale'] }
const pending = makeSale({ id: 142, status: 'PENDING_PAYMENT', amount_paid: '500.00', balance: '150.00' })
const walkIn = makeSale({ id: 143, customer: null, customer_name: null })

function serveSale(sale: ReturnType<typeof makeSale>) {
  server.use(http.get(api(`/sales/${sale.id}/`), () => HttpResponse.json(sale)))
}

describe('Sale details', () => {
  it('shows the sale, totals, payments and history', async () => {
    asUser(collector)
    serveSale({
      ...pending,
      events: [
        {
          id: 1,
          action: 'BACKDATED',
          changes: { sale_date: ['2026-11-28', '2026-11-27'] },
          reason: 'Paper receipt',
          performed_by: { id: 1, username: 'maria', display_name: 'Maria Reyes' },
          created_at: '2026-11-28T01:00:00Z',
        },
      ],
    })
    renderApp('/sales/142')

    expect(await screen.findByRole('heading', { name: /Sale #S20261127-000142/ })).toBeInTheDocument()
    expect(screen.getByText('Pending Payment')).toHaveClass('ar-badge--yellow')
    expect(screen.getByText(/Recorded 11\/27\/2026, 4:32 PM by maria/)).toBeInTheDocument()
    expect(screen.getByText('Juan Dela Cruz')).toBeInTheDocument()
    const totals = screen.getByLabelText('Totals')
    expect(totals).toHaveTextContent('Outstanding Balance₱150.00')
    expect(within(screen.getByRole('table', { name: 'Items' })).getByText('Super Grap')).toBeInTheDocument()
    expect(within(screen.getByRole('table', { name: 'Payments' })).getByText('Cash')).toBeInTheDocument()
    expect(screen.getByText('Backdated to 11/27/2026')).toBeInTheDocument()
    expect(screen.getByText(/Maria Reyes — Paper receipt/)).toBeInTheDocument()
  })

  it('records a payment toward the balance', async () => {
    asUser(collector)
    serveSale(pending)
    let body: unknown
    server.use(
      http.post(api('/sales/payments/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    const { user } = renderApp('/sales/142')
    await user.click(await screen.findByRole('button', { name: 'Record payment' }))
    const dialog = screen.getByRole('dialog', { name: 'Record Payment' })
    expect(within(dialog).getByLabelText(/Amount/)).toHaveValue('150.00')

    await user.clear(within(dialog).getByLabelText(/Amount/))
    await user.type(within(dialog).getByLabelText(/Amount/), '200')
    await user.selectOptions(within(dialog).getByLabelText(/Payment Method/), 'GCASH')
    await user.click(within(dialog).getByRole('button', { name: 'Record payment' }))
    expect(within(dialog).getByText(/can't be more than the balance of ₱150.00/)).toBeInTheDocument()

    await user.clear(within(dialog).getByLabelText(/Amount/))
    await user.type(within(dialog).getByLabelText(/Amount/), '150')
    await user.click(within(dialog).getByRole('button', { name: 'Record payment' }))

    expect(await screen.findByText(/Payment recorded for S20261127-000142. Balance is now ₱0.00./)).toBeInTheDocument()
    expect(body).toEqual({ sale: 142, amount: '150.00', payment_method: 'GCASH', reference_number: '' })
  })

  it('associates a customer to a walk-in sale with a reason', async () => {
    asUser()
    serveSale(walkIn)
    server.use(
      http.get(api('/customers/'), () => HttpResponse.json(page([{ id: 30, full_name: 'Ana Reyes', phone_number: '0918', email: '', is_active: true }]))),
    )
    let body: unknown
    server.use(
      http.post(api('/sales/143/customer/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...walkIn, customer: 30, customer_name: 'Ana Reyes' })
      }),
    )
    const { user } = renderApp('/sales/143')
    expect(await screen.findByText('Walk-in sale. No customer is linked.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Associate customer' }))
    const dialog = screen.getByRole('dialog', { name: 'Associate Customer' })
    const link = within(dialog).getByRole('button', { name: 'Link customer' })
    expect(link).toBeDisabled()
    await user.type(within(dialog).getByLabelText('Customer'), 'ana')
    await user.click(await within(dialog).findByRole('button', { name: /Ana Reyes/ }))
    await user.type(within(dialog).getByLabelText(/Reason for change/), 'Asked for a receipt')
    await user.click(link)

    expect(await screen.findByText(/Ana Reyes is now linked to S20261127-000143/)).toBeInTheDocument()
    expect(body).toEqual({ customer_id: 30, reason: 'Asked for a receipt' })
  })

  it('hides payment and cancel actions without permission', async () => {
    asUser()
    serveSale(pending)
    renderApp('/sales/142')
    await screen.findByRole('heading', { name: /Sale #/ })
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /cancel sale/i })).not.toBeInTheDocument()
  })

  it('opens drafts in the editor', async () => {
    asUser({ ...staffUser, permissions: ['sales.record_payment'] })
    serveSale(makeSale({ id: 150, status: 'DRAFT', sale_number: null, sale_date: null }))
    server.use(
      http.get(api('/products/'), () => HttpResponse.json(page([]))),
      http.get(api('/products/7/'), () => HttpResponse.json(makeProductDetail({ id: 7, name: 'BG66 Ultimax', selling_price: '450.00' }))),
      http.get(api('/products/9/'), () => HttpResponse.json(makeProductDetail({ id: 9, name: 'Super Grap', selling_price: '120.00' }))),
    )
    renderApp('/sales/150')

    expect(await screen.findByRole('heading', { name: 'Draft #150' })).toBeInTheDocument()
    const cart = screen.getByRole('region', { name: 'Cart' })
    await waitFor(() => expect(within(cart).getByText('BG66 Ultimax')).toBeInTheDocument())
    expect(screen.getByLabelText('Discount')).toHaveValue('40.00')
  })

  it('has no accessibility violations', async () => {
    asUser(collector)
    serveSale(pending)
    const { container } = renderApp('/sales/142')
    await screen.findByRole('heading', { name: /Sale #/ })
    await expectNoAxeViolations(container)
  })
})

describe('Reopened drafts (review fixes)', () => {
  const draft = makeSale({
    id: 150,
    status: 'DRAFT',
    sale_number: null,
    sale_date: null,
    discount_amount: '0.00',
    items: [
      { id: 1, product: 7, product_name: 'BG66 Ultimax', product_sku: 'B', quantity: 1, unit_selling_price: '450.00', discount_amount: '20.00', line_subtotal: '450.00', line_total: '430.00', created_at: '2026-11-27T08:32:00Z' },
    ],
  })

  function serveDraft(current = { price: '480.00', stock: 10, active: true }) {
    serveSale(draft)
    server.use(
      http.get(api('/products/'), () => HttpResponse.json(page([]))),
      http.get(api('/products/7/'), () =>
        HttpResponse.json({ ...makeProductDetail({ id: 7, name: 'BG66 Ultimax' }), selling_price: current.price, stock_quantity: current.stock, is_active: current.active }),
      ),
    )
  }

  it('uses current stock and price, keeps the line discount and explains the change', async () => {
    asUser({ ...staffUser, permissions: ['sales.record_payment'] })
    serveDraft()
    let body: unknown
    server.use(
      http.post(api('/sales/checkout/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(makeSale({ id: 150 }), { status: 201 })
      }),
    )
    const { user } = renderApp('/sales/150')

    expect(await screen.findByText('BG66 Ultimax now costs ₱480.00 (was ₱450.00).')).toBeInTheDocument()
    const cart = screen.getByRole('region', { name: 'Cart' })
    await user.click(within(cart).getByRole('button', { name: 'Increase BG66 Ultimax' }))
    expect(within(cart).getByText('×2')).toBeInTheDocument()
    expect(screen.getByLabelText('Totals')).toHaveTextContent('Total Due₱940.00')

    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    await waitFor(() => expect(body).toMatchObject({ draft_id: 150, items: [{ product_id: 7, quantity: 2, discount_amount: '20.00' }] }))
  })

  it('blocks completing a draft whose product is no longer sold', async () => {
    asUser({ ...staffUser, permissions: ['sales.record_payment'] })
    serveDraft({ price: '450.00', stock: 10, active: false })
    const { user } = renderApp('/sales/150')

    expect(await screen.findByText(/BG66 Ultimax is no longer sold/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    expect(screen.getByText('Remove products that are no longer sold.')).toBeInTheDocument()
  })

  it('still warns about unsaved changes after saving the draft', async () => {
    asUser({ ...staffUser, permissions: ['sales.record_payment'] })
    serveDraft()
    server.use(http.put(api('/sales/150/draft/'), () => HttpResponse.json(draft)))
    const { user } = renderApp('/sales/150')
    const cart = await screen.findByRole('region', { name: 'Cart' })

    // An unchanged draft can be left without a warning.
    await user.click(screen.getByRole('button', { name: /save draft/i }))
    expect(await screen.findByText('Draft #150 saved.')).toBeInTheDocument()

    await user.click(within(cart).getByRole('button', { name: 'Increase BG66 Ultimax' }))
    await user.click(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Inventory' }))
    expect(await screen.findByRole('dialog', { name: 'Leave this sale?' })).toBeInTheDocument()
  })
})
