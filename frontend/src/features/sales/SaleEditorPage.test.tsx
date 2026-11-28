import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeProduct, makeSale, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'
import { todayInStore } from '../../lib/format'

const cashier = { ...staffUser, permissions: ['sales.record_payment'] }
const manager = { ...staffUser, permissions: ['sales.record_payment', 'sales.backdate_sale'] }
const bg66 = makeProduct({ id: 7, name: 'BG66 Ultimax', subcategory: 'String', selling_price: '450.00', stock_quantity: 89 })
const grip = makeProduct({ id: 9, name: 'Super Grap', subcategory: 'Overgrip', selling_price: '120.00', stock_quantity: 56 })
const lastOne = makeProduct({ id: 11, name: 'Astrox 88D Pro', subcategory: 'Racket', selling_price: '11500.00', stock_quantity: 1 })
const soldOut = makeProduct({ id: 12, name: 'Aerosonic', stock_quantity: 0, stock_status: 'OUT_OF_STOCK' })
const juan = { id: 12, full_name: 'Juan Dela Cruz', phone_number: '0917 555 0123', email: '', is_active: true }

function serveCatalog() {
  server.use(
    http.get(api('/products/'), ({ request }) => {
      const search = new URL(request.url).searchParams.get('search')?.toLowerCase()
      const all = [bg66, grip, lastOne, soldOut]
      return HttpResponse.json(page(search ? all.filter((p) => p.name.toLowerCase().includes(search)) : all))
    }),
    http.get(api('/customers/'), () => HttpResponse.json(page([juan]))),
  )
}

function serveCheckout(capture: (body: Record<string, unknown>) => void, sale = makeSale({ id: 142 })) {
  server.use(
    http.post(api('/sales/checkout/'), async ({ request }) => {
      capture((await request.json()) as Record<string, unknown>)
      return HttpResponse.json(sale, { status: 201 })
    }),
    http.get(api('/sales/142/'), () => HttpResponse.json(sale)),
  )
}

async function addToCart(user: ReturnType<typeof renderApp>['user'], name: string, times = 1) {
  const button = await screen.findByRole('button', { name: `Add ${name}` })
  for (let i = 0; i < times; i++) await user.click(button)
}

describe('Create Sale', () => {
  it('rings up a paid sale with a linked customer and a discount', async () => {
    asUser(cashier)
    serveCatalog()
    let body: Record<string, unknown> = {}
    serveCheckout((b) => (body = b))
    const { user, currentPath } = renderApp('/sales/new')
    expect(await screen.findByRole('heading', { level: 1, name: 'Create Sale' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Customer'), 'juan')
    await user.click(await screen.findByRole('button', { name: /Juan Dela Cruz/ }))
    await addToCart(user, 'BG66 Ultimax')
    await addToCart(user, 'Super Grap', 2)
    await user.type(screen.getByLabelText('Discount'), '40')

    const totals = screen.getByLabelText('Totals')
    expect(totals).toHaveTextContent('₱690.00')
    expect(totals).toHaveTextContent('-₱40.00')
    expect(totals).toHaveTextContent('₱650.00')

    await user.selectOptions(screen.getByLabelText('Payment Method'), 'CASH')
    await user.type(screen.getByLabelText('Amount Paid'), '650')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))

    expect(await screen.findByText(/Sale S20261127-000142 completed — balance ₱0.00/)).toBeInTheDocument()
    await waitFor(() => expect(currentPath()).toBe('/sales/142'))
    expect(body).toMatchObject({
      customer_id: 12,
      items: [
        { product_id: 7, quantity: 1 },
        { product_id: 9, quantity: 2 },
      ],
      discount_amount: '40.00',
      sale_date: todayInStore(),
      backdate_reason: '',
      payment: { payment_method: 'CASH', amount: '650.00' },
      draft_id: null,
    })
    expect(String(body.client_transaction_id)).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('caps adds at the available stock and disables sold-out products', async () => {
    asUser(cashier)
    serveCatalog()
    const { user } = renderApp('/sales/new')

    await addToCart(user, 'Astrox 88D Pro')
    expect(await screen.findByRole('button', { name: 'Add Astrox 88D Pro' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Aerosonic is out of stock' })).toBeDisabled()
    const cart = screen.getByRole('region', { name: 'Cart' })
    expect(within(cart).getByRole('button', { name: 'Increase Astrox 88D Pro' })).toBeDisabled()
  })

  it('validates before sending and reuses the transaction id after a network error', async () => {
    asUser(cashier)
    serveCatalog()
    const bodies: Record<string, unknown>[] = []
    let fail = true
    server.use(
      http.post(api('/sales/checkout/'), async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>)
        if (fail) {
          fail = false
          return HttpResponse.error()
        }
        return HttpResponse.json(makeSale({ id: 142, status: 'PENDING_PAYMENT', balance: '450.00' }), { status: 201 })
      }),
      http.get(api('/sales/142/'), () => HttpResponse.json(makeSale({ id: 142 }))),
    )
    const { user } = renderApp('/sales/new')

    await user.click(await screen.findByRole('button', { name: 'Complete sale' }))
    expect(screen.getByText('Add at least one product.')).toBeInTheDocument()
    expect(bodies).toHaveLength(0)

    await addToCart(user, 'BG66 Ultimax')
    await user.type(screen.getByLabelText('Amount Paid'), '500')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    expect(screen.getByText('Choose how the customer paid.')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Payment Method'), 'CASH')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    expect(screen.getByText(/Amount paid can't be more than the total/)).toBeInTheDocument()

    // No payment now: the sale is saved as Pending Payment.
    await user.clear(screen.getByLabelText('Amount Paid'))
    await user.selectOptions(screen.getByLabelText('Payment Method'), '')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server')
    expect(screen.getByLabelText('Cart')).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    expect(await screen.findByText(/saved as Pending Payment — balance ₱450.00/)).toBeInTheDocument()
    expect(bodies).toHaveLength(2)
    expect(bodies[0]!.client_transaction_id).toBe(bodies[1]!.client_transaction_id)
  })

  it('keeps the cart and names the product on a stock shortage', async () => {
    asUser(cashier)
    serveCatalog()
    server.use(
      http.post(api('/sales/checkout/'), () =>
        HttpResponse.json({ items: ['Insufficient stock for BG66 Ultimax. Available: 0, requested change: -1.'] }, { status: 400 }),
      ),
    )
    const { user } = renderApp('/sales/new')
    await addToCart(user, 'BG66 Ultimax')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))

    expect(await screen.findByText(/Insufficient stock for BG66 Ultimax/)).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Cart' })).getByText('BG66 Ultimax')).toBeInTheDocument()
  })

  it('creates a customer inline', async () => {
    asUser(cashier)
    serveCatalog()
    let created: unknown
    server.use(
      http.post(api('/customers/'), async ({ request }) => {
        created = await request.json()
        return HttpResponse.json({ ...juan, id: 30, full_name: 'Ana Reyes', phone_number: '0918', duplicate_phone_customers: [] }, { status: 201 })
      }),
    )
    const { user } = renderApp('/sales/new')
    await user.click(await screen.findByRole('button', { name: 'New customer' }))
    await user.type(screen.getByLabelText(/Customer Name/), 'Ana Reyes')
    await user.type(screen.getByLabelText('Customer Contact #'), '0918')
    await user.click(screen.getByRole('button', { name: 'Save customer' }))

    expect(await screen.findByRole('group', { name: 'Customer' })).toHaveTextContent('Ana Reyes')
    expect(created).toEqual({ full_name: 'Ana Reyes', phone_number: '0918' })
  })

  it('hides payment fields without the record-payment permission and shows a read-only date', async () => {
    asUser()
    serveCatalog()
    renderApp('/sales/new')

    expect(await screen.findByText(/You can't record payments/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Amount Paid')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Date of Sale')).toHaveAttribute('readonly')
  })

  it('lets managers backdate with a reason, and blocks future dates', async () => {
    asUser(manager)
    serveCatalog()
    let body: Record<string, unknown> = {}
    serveCheckout((b) => (body = b))
    const { user } = renderApp('/sales/new')
    await addToCart(user, 'Super Grap')

    const date = screen.getByLabelText('Date of Sale')
    expect(date).toHaveAttribute('max', todayInStore())
    await user.clear(date)
    await user.type(date, '2026-11-20')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    expect(await screen.findByText('Explain why this sale has a past date.')).toBeInTheDocument()

    await user.type(screen.getByLabelText(/Reason for past date/), 'Paper receipt')
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))
    await waitFor(() => expect(body).toMatchObject({ sale_date: '2026-11-20', backdate_reason: 'Paper receipt' }))
  })

  it('saves a draft', async () => {
    asUser(cashier)
    serveCatalog()
    let body: unknown
    server.use(
      http.post(api('/sales/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(makeSale({ id: 142, status: 'DRAFT', sale_number: null, sale_date: null }), { status: 201 })
      }),
      http.get(api('/sales/142/'), () => HttpResponse.json(makeSale({ id: 142, status: 'DRAFT', sale_number: null, sale_date: null }))),
    )
    const { user } = renderApp('/sales/new')
    await addToCart(user, 'Super Grap')
    await user.click(screen.getByRole('button', { name: /save draft/i }))

    expect(await screen.findByText('Draft #142 saved.')).toBeInTheDocument()
    expect(body).toEqual({ customer_id: null, items: [{ product_id: 9, quantity: 1 }], discount_amount: '0.00' })
  })

  it('asks before leaving a non-empty cart', async () => {
    asUser(cashier)
    serveCatalog()
    const { user, currentPath } = renderApp('/sales/new')
    await addToCart(user, 'Super Grap')

    await user.click(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Inventory' }))
    const dialog = await screen.findByRole('dialog', { name: 'Leave this sale?' })
    await user.click(within(dialog).getByRole('button', { name: 'Stay' }))
    expect(currentPath()).toBe('/sales/new')
    expect(within(screen.getByRole('region', { name: 'Cart' })).getByText('Super Grap')).toBeInTheDocument()
  })

  it('can be completed with the keyboard', async () => {
    asUser(cashier)
    serveCatalog()
    let body: Record<string, unknown> = {}
    serveCheckout((b) => (body = b))
    const { user } = renderApp('/sales/new')
    const add = await screen.findByRole('button', { name: 'Add Super Grap' })
    add.focus()
    await user.keyboard('{Enter}')
    screen.getByRole('button', { name: 'Complete sale' }).focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(body).toHaveProperty('items'))
  })

  it('has no accessibility violations', async () => {
    asUser(manager)
    serveCatalog()
    const { container } = renderApp('/sales/new')
    await screen.findByRole('button', { name: 'Add BG66 Ultimax' })
    await expectNoAxeViolations(container)
  })
})

describe('Create Sale review fixes', () => {
  afterEach(() => vi.useRealTimers())

  it('uses the new day when the page was left open past midnight', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date('2026-11-28T15:50:00Z') }) // 23:50 in Manila
    asUser(cashier)
    serveCatalog()
    let body: Record<string, unknown> = {}
    serveCheckout((b) => (body = b))
    const { user } = renderApp('/sales/new')
    expect(await screen.findByLabelText('Date of Sale')).toHaveValue('2026-11-28')
    await addToCart(user, 'Super Grap')

    vi.setSystemTime(new Date('2026-11-28T16:05:00Z')) // 00:05 the next day in Manila
    await user.click(screen.getByRole('button', { name: 'Complete sale' }))

    await waitFor(() => expect(body).toMatchObject({ sale_date: '2026-11-29', backdate_reason: '' }))
  })
})
