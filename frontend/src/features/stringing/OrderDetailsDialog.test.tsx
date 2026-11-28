import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { StringingOrder } from '../../api/stringing'
import { expectNoAxeViolations } from '../../test/axe'
import { makeStringingOrder, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const manager = {
  ...staffUser,
  permissions: ['sales.record_payment', 'sales.process_refund', 'stringing.cancel_stringingorder'],
}

const inProgress = makeStringingOrder({
  status: 'IN_PROGRESS',
  status_display: 'In Progress',
  string_from_store: true,
  string_color: 'White',
  has_stencil: true,
  stencil_price: '50.00',
  has_grip: true,
  grip_price: '120.00',
  add_ons_total: '170.00',
  discount_amount: '100.00',
  total_amount: '420.00',
  amount_paid: '270.00',
  balance: '150.00',
})

const payment = {
  id: 1,
  amount: '270.00',
  payment_method: 'GCASH',
  payment_type: 'RECEIPT',
  status: 'POSTED',
  payment_date: '2026-11-19T02:05:00Z',
  reference_number: '',
  notes: '',
  received_by: { id: 1, username: 'maria' },
}

/** Serves the list plus one order whose detail can change over time. */
function serve(initial: StringingOrder) {
  const state = { order: initial }
  server.use(
    http.get(api('/stringing/orders/'), () => HttpResponse.json(page([state.order]))),
    http.get(api('/stringing/orders/status-counts/'), () => HttpResponse.json({ all: 1, RECEIVED: 0, IN_PROGRESS: 1, READY: 0, COMPLETED: 0, CANCELLED: 0 })),
    http.get(api(`/stringing/orders/${initial.id}/`), () => HttpResponse.json(state.order)),
    http.get(api(`/stringing/orders/${initial.id}/payments/`), () => HttpResponse.json(page([payment]))),
  )
  return state
}

async function openDetails(order: StringingOrder) {
  const utils = renderApp(`/stringing?order=${order.id}`)
  const dialog = await screen.findByRole('dialog', { name: `Order ${order.order_number}` })
  return { ...utils, dialog }
}

describe('Order details', () => {
  it('shows the stepper, details, amounts and payments', async () => {
    asUser(manager)
    serve(inProgress)
    const { dialog } = await openDetails(inProgress)
    const steps = within(dialog).getByRole('list', { name: 'Progress' })
    expect(within(steps).getByText('In Progress')).toHaveAttribute('aria-current', 'step')
    expect(within(steps).getByText('Received')).toHaveClass('ar-stepper__step--done')
    expect(within(steps).getByText('Ready for Pickup')).not.toHaveClass('ar-stepper__step--done')
    expect(dialog).toHaveTextContent('Juan Dela Cruz')
    expect(dialog).toHaveTextContent('0917 555 0123')
    expect(dialog).toHaveTextContent('BG80 (store-bought)')
    expect(dialog).toHaveTextContent('White')
    expect(dialog).toHaveTextContent('Stencil, Grip')
    const amounts = within(dialog).getByLabelText('Amounts')
    expect(amounts).toHaveTextContent('Store-string discount-₱100.00')
    expect(amounts).toHaveTextContent('Add-ons (stencil, grip)₱170.00')
    expect(amounts).toHaveTextContent('Amount paid-₱270.00')
    expect(amounts).toHaveTextContent('Balance due₱150.00')
    expect(amounts).not.toHaveTextContent('Direct cost')
    expect(await within(dialog).findByText(/Payment · GCash/)).toBeInTheDocument()
  })

  it('offers only allowed moves and sends the status the user saw', async () => {
    asUser(manager)
    const state = serve(inProgress)
    let body: unknown
    server.use(
      http.post(api('/stringing/orders/126/status/'), async ({ request }) => {
        body = await request.json()
        state.order = { ...state.order, status: 'READY', status_display: 'Ready for Pickup' }
        return HttpResponse.json(state.order)
      }),
    )
    const { user, dialog, currentPath } = await openDetails(inProgress)
    const select = within(dialog).getByLabelText('Update status')
    const options = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['Choose the next status', 'Ready for Pickup', 'Received'])
    await user.selectOptions(select, 'READY')
    await user.click(within(dialog).getByRole('button', { name: 'Save status' }))
    expect(await screen.findByText('Order STR-2026-000126 is now Ready for Pickup.')).toBeInTheDocument()
    expect(body).toEqual({ status: 'READY', expected_status: 'IN_PROGRESS' })
    await waitFor(() => expect(currentPath()).toBe('/stringing'))
  })

  it('reports a conflicting status change and refreshes', async () => {
    asUser(manager)
    const state = serve(inProgress)
    server.use(
      http.post(api('/stringing/orders/126/status/'), () => {
        state.order = { ...state.order, status: 'READY', status_display: 'Ready for Pickup' }
        return HttpResponse.json(
          { detail: "This order's status was changed by someone else. It is now Ready for Pickup.", current_status: 'READY' },
          { status: 400 },
        )
      }),
    )
    const { user, dialog } = await openDetails(inProgress)
    await user.selectOptions(within(dialog).getByLabelText('Update status'), 'RECEIVED')
    await user.click(within(dialog).getByRole('button', { name: 'Save status' }))
    expect(await within(dialog).findByText(/changed by someone else. It is now Ready for Pickup/)).toBeInTheDocument()
    await waitFor(() => expect(within(dialog).getByText('Ready for Pickup', { selector: '.ar-badge' })).toBeInTheDocument())
  })

  it('blocks completion while a balance is due, and records the payment', async () => {
    asUser(manager)
    const ready = { ...inProgress, status: 'READY' as const, status_display: 'Ready for Pickup' }
    const state = serve(ready)
    let body: unknown
    server.use(
      http.post(api('/stringing/orders/126/payments/'), async ({ request }) => {
        body = await request.json()
        state.order = { ...state.order, amount_paid: '420.00', balance: '0.00', payment_state: 'PAID' }
        return HttpResponse.json({ payment: { ...payment, id: 2 }, order: state.order }, { status: 201 })
      }),
    )
    const { user, dialog } = await openDetails(ready)
    await user.selectOptions(within(dialog).getByLabelText('Update status'), 'COMPLETED')
    expect(within(dialog).getByText(/A balance of ₱150.00 must be paid before pickup/)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Save status' })).toBeDisabled()

    await user.click(within(dialog).getByRole('button', { name: 'Record payment' }))
    const pay = await screen.findByRole('dialog', { name: 'Record Payment' })
    expect(within(pay).getByLabelText(/Amount/)).toHaveValue('150.00')
    await user.selectOptions(within(pay).getByLabelText(/Payment Method/), 'CASH')
    await user.click(within(pay).getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText('Payment recorded for STR-2026-000126. Balance is now ₱0.00.')).toBeInTheDocument()
    expect(body).toMatchObject({ payment_type: 'RECEIPT', amount: '150.00', payment_method: 'CASH' })
    await waitFor(() => expect(within(dialog).getByLabelText('Amounts')).toHaveTextContent('Balance due₱0.00'))
  })

  it('shows a cancelled order read only, with its reason and materials, and records a refund', async () => {
    asUser(manager)
    const cancelled = makeStringingOrder({
      status: 'CANCELLED',
      status_display: 'Cancelled',
      cancelled_at: '2026-11-20T03:00:00Z',
      cancelled_by: { id: 2, username: 'ana' },
      cancellation_reason: 'Customer changed mind',
      materials_used: true,
      amount_paid: '270.00',
      balance: '0.00',
      refund_due: '270.00',
    })
    serve(cancelled)
    let body: unknown
    server.use(
      http.post(api('/stringing/orders/126/payments/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ payment: { ...payment, id: 3 }, order: { ...cancelled, refund_due: '0.00' } }, { status: 201 })
      }),
    )
    const { user, dialog } = await openDetails(cancelled)
    expect(dialog).toHaveTextContent('by ana. Reason: Customer changed mind. Materials already used.')
    expect(within(dialog).queryByLabelText('Update status')).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Save status' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('link', { name: 'Cancel order' })).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText('Amounts')).toHaveTextContent('Refund due₱270.00')

    await user.click(within(dialog).getByRole('button', { name: 'Record refund' }))
    const refund = await screen.findByRole('dialog', { name: 'Record Refund' })
    await user.selectOptions(within(refund).getByLabelText(/Payment Method/), 'GCASH')
    await user.click(within(refund).getByRole('button', { name: 'Record refund' }))
    expect(await within(refund).findByText('Enter a reason for the refund.')).toBeInTheDocument()
    await user.type(within(refund).getByLabelText(/Reason/), 'Deposit returned')
    await user.click(within(refund).getByRole('button', { name: 'Record refund' }))
    expect(await screen.findByText('Refund recorded for STR-2026-000126. Refund due is now ₱0.00.')).toBeInTheDocument()
    expect(body).toMatchObject({ payment_type: 'REFUND', amount: '270.00', payment_method: 'GCASH', reason: 'Deposit returned' })
  })

  it('hides payment, refund and cancel actions without the permissions', async () => {
    asUser()
    serve(inProgress)
    const { dialog } = await openDetails(inProgress)
    expect(within(dialog).queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('link', { name: 'Cancel order' })).not.toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Edit' })).toBeInTheDocument()
  })

  it('shows direct cost and profit only with the financials permission', async () => {
    asUser({ ...staffUser, permissions: ['stringing.view_stringing_financials'] })
    const order = { ...inProgress, direct_cost: '180.00', profit: '240.00' }
    serve(order)
    const { dialog } = await openDetails(order)
    expect(within(dialog).getByLabelText('Amounts')).toHaveTextContent('Direct cost / profit₱180.00 / ₱240.00')
  })

  it('closes back to the list, keeping its filters', async () => {
    asUser(manager)
    serve(inProgress)
    const { user, currentPath } = renderApp('/stringing?status=IN_PROGRESS&order=126')
    const dialog = await screen.findByRole('dialog', { name: 'Order STR-2026-000126' })
    await user.click(within(dialog.querySelector('footer')!).getByRole('button', { name: 'Close' }))
    await waitFor(() => expect(currentPath()).toBe('/stringing?status=IN_PROGRESS'))
  })

  it('has no accessibility violations', async () => {
    asUser(manager)
    serve(inProgress)
    const { container, dialog } = await openDetails(inProgress)
    await within(dialog).findByText(/Payment · GCash/)
    await expectNoAxeViolations(container)
  })
})
