import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeStringingOrder, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const cashier = { ...staffUser, permissions: ['sales.record_payment'] }

function serveList() {
  server.use(
    http.get(api('/stringing/orders/'), () => HttpResponse.json(page([]))),
    http.get(api('/stringing/orders/status-counts/'), () => HttpResponse.json({ all: 0, RECEIVED: 0, IN_PROGRESS: 0, READY: 0, COMPLETED: 0, CANCELLED: 0 })),
    http.get(api('/stringing/orders/:id/payments/'), () => HttpResponse.json(page([]))),
  )
}

describe('Create a Stringing Order', () => {
  it('updates the invoice as add-ons are ticked and prices overridden', async () => {
    asUser(cashier)
    const { user } = renderApp('/stringing/new')
    expect(await screen.findByRole('heading', { level: 1, name: 'Create a Stringing Order' })).toBeInTheDocument()
    const panel = screen.getByLabelText('Invoice')
    expect(panel).toHaveTextContent('Stringing service₱350.00')
    expect(panel).toHaveTextContent('Total₱350.00')

    await user.click(screen.getByLabelText('Add Stencil'))
    await user.click(screen.getByLabelText('Add Grip'))
    await user.click(screen.getByLabelText(/String bought from store/))
    expect(panel).toHaveTextContent('Store-string discount-₱100.00')
    expect(panel).toHaveTextContent('Stencil₱50.00')
    expect(panel).toHaveTextContent('Grip₱120.00')
    expect(panel).toHaveTextContent('Total₱420.00')

    const grip = screen.getByLabelText(/Grip Price/)
    await user.clear(grip)
    await user.type(grip, '100')
    expect(panel).toHaveTextContent('Total₱400.00')
    await user.type(screen.getByLabelText('Deposit / payment received'), '270')
    expect(screen.getByText('Balance due').parentElement).toHaveTextContent('₱130.00')
  })

  it('shows field errors and saves nothing when required fields are missing', async () => {
    asUser(cashier)
    let posted = false
    server.use(http.post(api('/stringing/orders/'), () => ((posted = true), HttpResponse.json({}, { status: 500 }))))
    const { user } = renderApp('/stringing/new')
    await user.type(await screen.findByLabelText('Deposit / payment received'), '100')
    await user.click(screen.getByRole('button', { name: 'Create order' }))
    expect(await screen.findByText('Enter the racket model.')).toBeInTheDocument()
    expect(screen.getByText('Enter the string model.')).toBeInTheDocument()
    expect(screen.getByText('Choose how the customer paid.')).toBeInTheDocument()
    expect(posted).toBe(false)
  })

  it('creates the order with a deposit once, even on a double click, then opens it', async () => {
    asUser(cashier)
    serveList()
    const bodies: Record<string, unknown>[] = []
    const created = makeStringingOrder({ id: 130, has_stencil: true, stencil_price: '50.00', amount_paid: '270.00', balance: '130.00', total_amount: '400.00' })
    server.use(
      http.post(api('/stringing/orders/'), async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>)
        return HttpResponse.json(created, { status: bodies.length === 1 ? 201 : 200 })
      }),
      http.get(api('/stringing/orders/130/'), () => HttpResponse.json(created)),
    )
    const { user, currentPath } = renderApp('/stringing/new')
    await user.type(await screen.findByLabelText(/Racket Model/), 'Arcsaber 11')
    await user.type(screen.getByLabelText(/String Model/), 'BG80')
    await user.type(screen.getByLabelText('String Color'), 'White')
    await user.type(screen.getByLabelText('Tension (lbs)'), '27 lbs')
    await user.click(screen.getByLabelText('Add Stencil'))
    await user.type(screen.getByLabelText('Deposit / payment received'), '270')
    await user.selectOptions(screen.getByLabelText('Payment Method'), 'GCASH')
    const create = screen.getByRole('button', { name: 'Create order' })
    fireEvent.click(create)
    fireEvent.click(create)

    expect(await screen.findByText('Order STR-2026-000130 created. Balance due ₱130.00.')).toBeInTheDocument()
    await waitFor(() => expect(currentPath()).toBe('/stringing?order=130'))
    expect(bodies).toHaveLength(1)
    expect(bodies[0]).toMatchObject({
      racket_description: 'Arcsaber 11',
      string_type: 'BG80',
      string_color: 'White',
      tension: '27 lbs',
      service_price: '350.00',
      has_stencil: true,
      stencil_price: '50.00',
      has_grip: false,
      grip_price: '0.00',
      deposit: { amount: '270.00', payment_method: 'GCASH', reference_number: '' },
    })
    expect(bodies[0]!.client_transaction_id).toMatch(/[0-9a-f-]{36}/)
    expect(await screen.findByRole('dialog', { name: 'Order STR-2026-000130' })).toBeInTheDocument()
  })

  it('shows server field errors next to the fields', async () => {
    asUser(cashier)
    server.use(
      http.post(api('/stringing/orders/'), () =>
        HttpResponse.json({ deposit: ['Deposit cannot be more than the order total.'], racket_description: ['Too long.'] }, { status: 400 }),
      ),
    )
    const { user } = renderApp('/stringing/new')
    await user.type(await screen.findByLabelText(/Racket Model/), 'R')
    await user.type(screen.getByLabelText(/String Model/), 'S')
    await user.click(screen.getByRole('button', { name: 'Create order' }))
    expect(await screen.findByText('Deposit cannot be more than the order total.')).toBeInTheDocument()
    expect(screen.getByText('Too long.')).toBeInTheDocument()
  })

  it('hides the deposit without the payment permission', async () => {
    asUser()
    renderApp('/stringing/new')
    expect(await screen.findByText(/You can't record payments/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Deposit / payment received')).not.toBeInTheDocument()
  })

  it('asks before leaving with unsaved input', async () => {
    asUser(cashier)
    serveList()
    const { user, currentPath } = renderApp('/stringing/new')
    await user.type(await screen.findByLabelText(/Racket Model/), 'Arcsaber 11')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    const dialog = await screen.findByRole('dialog', { name: 'Leave this order?' })
    await user.click(within(dialog).getByRole('button', { name: 'Stay' }))
    expect(currentPath()).toBe('/stringing/new')
    expect(screen.getByLabelText(/Racket Model/)).toHaveValue('Arcsaber 11')
  })

  it('edits an open order, sending only the changes and offering no deposit', async () => {
    asUser(cashier)
    serveList()
    const order = makeStringingOrder({ has_stencil: true, stencil_price: '50.00' })
    let body: unknown
    server.use(
      http.get(api('/stringing/orders/126/'), () => HttpResponse.json(order)),
      http.patch(api('/stringing/orders/126/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...order, tension: '28 lbs', has_stencil: false, stencil_price: '0.00' })
      }),
    )
    const { user, currentPath } = renderApp('/stringing/126/edit')
    expect(await screen.findByRole('heading', { level: 1, name: 'Edit Stringing Order' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Deposit / payment received')).not.toBeInTheDocument()
    const tension = await screen.findByLabelText('Tension (lbs)')
    await user.clear(tension)
    await user.type(tension, '28 lbs')
    await user.click(screen.getByLabelText('Add Stencil'))
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(currentPath()).toBe('/stringing?order=126'))
    expect(body).toEqual({ tension: '28 lbs', has_stencil: false, stencil_price: '0.00' })
  })

  it('refuses to edit a completed order', async () => {
    asUser(cashier)
    server.use(http.get(api('/stringing/orders/126/'), () => HttpResponse.json(makeStringingOrder({ status: 'COMPLETED', status_display: 'Completed' }))))
    renderApp('/stringing/126/edit')
    expect(await screen.findByText(/is Completed and can no longer be edited/)).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    asUser(cashier)
    const { container } = renderApp('/stringing/new')
    await screen.findByLabelText(/Racket Model/)
    await expectNoAxeViolations(container)
  })
})
