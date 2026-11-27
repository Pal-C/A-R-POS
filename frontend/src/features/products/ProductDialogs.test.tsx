import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeProduct, page } from '../../test/fixtures'
import { api, asUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const aerosonic = makeProduct({ id: 4, name: 'Aerosonic', subcategory: 'String', selling_price: '420.00', stock_quantity: 0, stock_status: 'OUT_OF_STOCK' })
const bg66 = makeProduct({ id: 7, name: 'BG66 Ultimax', stock_quantity: 89 })
const oldGrip = makeProduct({ id: 9, name: 'Old Grip', is_active: false })

function serveList() {
  let listCalls = 0
  server.use(
    http.get(api('/products/'), ({ request }) => {
      listCalls++
      const active = new URL(request.url).searchParams.get('is_active')
      return HttpResponse.json(page(active === 'false' ? [oldGrip] : [bg66, aerosonic]))
    }),
  )
  return () => listCalls
}

describe('Remove Product dialog', () => {
  it('requires a reason and the confirmation, then deactivates and refreshes', async () => {
    asUser()
    const listCalls = serveList()
    let body: unknown
    server.use(
      http.post(api('/products/4/deactivate/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ detail: 'ok', product: { ...aerosonic, is_active: false } })
      }),
    )
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: 'Remove Aerosonic' }))

    const dialog = screen.getByRole('dialog', { name: 'Remove Product' })
    expect(dialog).toHaveTextContent('Aerosonic (String)')
    expect(dialog).toHaveTextContent('Stock: 0')
    expect(within(dialog).getByText('Out of Stock')).toBeInTheDocument()
    const confirm = within(dialog).getByRole('button', { name: 'Remove product' })
    expect(confirm).toBeDisabled()

    await user.type(within(dialog).getByLabelText(/Reason for removal/), 'Discontinued by supplier')
    expect(confirm).toBeDisabled()
    await user.click(within(dialog).getByLabelText('Are you sure? This hides the product from POS'))
    expect(confirm).toBeEnabled()
    const callsBefore = listCalls()
    await user.click(confirm)

    expect(await screen.findByText('Aerosonic was removed from sale.')).toBeInTheDocument()
    expect(body).toEqual({ reason: 'Discontinued by supplier' })
    expect(screen.queryByRole('dialog', { name: 'Remove Product' })).not.toBeInTheDocument()
    await waitFor(() => expect(listCalls()).toBeGreaterThan(callsBefore))
  })

  it('warns when the product still has stock', async () => {
    asUser()
    serveList()
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: 'Remove BG66 Ultimax' }))
    expect(screen.getByRole('note')).toHaveTextContent('still has 89 in stock')
  })

  it('closes on Escape and returns focus to the row action', async () => {
    asUser()
    serveList()
    const { user } = renderApp('/inventory')
    const action = await screen.findByRole('button', { name: 'Remove Aerosonic' })
    await user.click(action)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Remove Product' })).not.toBeInTheDocument()
    expect(action).toHaveFocus()
  })

  it('shows a server error inside the dialog', async () => {
    asUser()
    serveList()
    server.use(http.post(api('/products/4/deactivate/'), () => HttpResponse.json({ detail: 'x' }, { status: 403 })))
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: 'Remove Aerosonic' }))
    const dialog = screen.getByRole('dialog', { name: 'Remove Product' })
    await user.type(within(dialog).getByLabelText(/Reason for removal/), 'x')
    await user.click(within(dialog).getByRole('checkbox'))
    await user.click(within(dialog).getByRole('button', { name: 'Remove product' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent("You don't have permission to do that.")
  })

  it('has no accessibility violations', async () => {
    asUser()
    serveList()
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: 'Remove Aerosonic' }))
    await expectNoAxeViolations(screen.getByRole('dialog', { name: 'Remove Product' }))
  })
})

describe('Reactivate Product dialog', () => {
  it('requires a reason and reactivates', async () => {
    asUser()
    serveList()
    let body: unknown
    server.use(
      http.post(api('/products/9/reactivate/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ detail: 'ok', product: { ...oldGrip, is_active: true } })
      }),
    )
    const { user } = renderApp('/inventory?availability=inactive')
    await user.click(await screen.findByRole('button', { name: 'Reactivate Old Grip' }))

    const dialog = screen.getByRole('dialog', { name: 'Reactivate Product' })
    const confirm = within(dialog).getByRole('button', { name: 'Reactivate product' })
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText(/Reason for reactivation/), 'Back in range')
    await user.click(confirm)

    expect(await screen.findByText('Old Grip is active again.')).toBeInTheDocument()
    expect(body).toEqual({ reason: 'Back in range' })
  })
})

describe('Receive Stock dialog', () => {
  it('validates the quantity and records the restock', async () => {
    asUser()
    serveList()
    let body: unknown
    server.use(
      http.post(api('/inventory/restocks/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(
          { id: 1, product_id: 7, product_name: 'BG66 Ultimax', quantity_change: 10, quantity_after: 99 },
          { status: 201 },
        )
      }),
    )
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: /receive stock/i }))

    const dialog = screen.getByRole('dialog', { name: 'Receive Stock' })
    await user.click(within(dialog).getByRole('button', { name: 'Receive stock' }))
    expect(within(dialog).getByText('Choose a product.')).toBeInTheDocument()
    expect(within(dialog).getByText('Enter a quantity of 1 or more.')).toBeInTheDocument()
    expect(body).toBeUndefined()

    await user.selectOptions(await within(dialog).findByLabelText(/Product/), '7')
    await user.type(within(dialog).getByLabelText(/Quantity received/), '10')
    await user.type(within(dialog).getByLabelText('Reference number'), 'DR-1001')
    await user.click(within(dialog).getByRole('button', { name: 'Receive stock' }))

    expect(await screen.findByText('Received 10 × BG66 Ultimax. Stock is now 99.')).toBeInTheDocument()
    expect(body).toEqual({ product_id: 7, quantity_received: 10, reference_number: 'DR-1001' })
  })

  it('shows a busy state while saving', async () => {
    asUser()
    serveList()
    let release: () => void = () => {}
    server.use(
      http.post(api('/inventory/restocks/'), async () => {
        await new Promise<void>((resolve) => {
          release = resolve
        })
        return HttpResponse.json({ product_name: 'BG66 Ultimax', quantity_after: 90 }, { status: 201 })
      }),
    )
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: /receive stock/i }))
    const dialog = screen.getByRole('dialog', { name: 'Receive Stock' })
    await user.selectOptions(await within(dialog).findByLabelText(/Product/), '7')
    await user.type(within(dialog).getByLabelText(/Quantity received/), '1')
    await user.click(within(dialog).getByRole('button', { name: 'Receive stock' }))

    await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Receive stock' })).toBeDisabled())
    expect(within(dialog).getByRole('button', { name: 'Close' })).toBeDisabled()
    release()
    expect(await screen.findByText(/Stock is now 90/)).toBeInTheDocument()
  })

  it('keeps the chosen product when searching again', async () => {
    asUser()
    serveList()
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: /receive stock/i }))
    const dialog = screen.getByRole('dialog', { name: 'Receive Stock' })
    await user.selectOptions(await within(dialog).findByLabelText(/Product/), '7')
    let searched = false
    server.use(
      http.get(api('/products/'), ({ request }) => {
        if (new URL(request.url).searchParams.get('search') === 'aero') searched = true
        return HttpResponse.json(page([aerosonic]))
      }),
    )
    await user.type(within(dialog).getByLabelText('Find a product'), 'aero')
    await waitFor(() => expect(searched).toBe(true))
    // Let the new results render before checking the selection survived.
    await waitFor(() => expect(within(dialog).getAllByRole('option').length).toBeGreaterThan(0))
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(within(dialog).getByLabelText(/Product/)).toHaveValue('7')
    expect(within(dialog).getByRole('option', { name: /BG66 Ultimax/ })).toBeInTheDocument()
  })

  it('shows a reason error from the server in the dialog', async () => {
    asUser()
    serveList()
    server.use(
      http.post(api('/products/4/deactivate/'), () => HttpResponse.json({ reason: ['A reason is required.'] }, { status: 400 })),
    )
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: 'Remove Aerosonic' }))
    const dialog = screen.getByRole('dialog', { name: 'Remove Product' })
    await user.type(within(dialog).getByLabelText(/Reason for removal/), 'x')
    await user.click(within(dialog).getByRole('checkbox'))
    await user.click(within(dialog).getByRole('button', { name: 'Remove product' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('A reason is required.')
  })

  it('has no accessibility violations', async () => {
    asUser()
    serveList()
    const { user } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: /receive stock/i }))
    await expectNoAxeViolations(screen.getByRole('dialog', { name: 'Receive Stock' }))
  })
})
