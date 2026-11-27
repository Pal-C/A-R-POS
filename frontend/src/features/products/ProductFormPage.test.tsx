import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeProduct, makeProductDetail } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const manager = { ...staffUser, permissions: ['catalog.view_product_cost', 'catalog.adjust_stock'] }

describe('Add Product', () => {
  async function fillRequired(user: ReturnType<typeof renderApp>['user'], { cost = true } = {}) {
    await user.type(await screen.findByLabelText(/Product Name/), 'BG66 Ultimax')
    await user.selectOptions(screen.getByLabelText(/Category/), 'ACCESSORIES')
    await user.type(screen.getByLabelText('Type'), 'String')
    if (cost) await user.type(screen.getByLabelText(/Cost of Sale/), '320')
    await user.type(screen.getByLabelText(/Selling Price/), '450')
    await user.clear(screen.getByLabelText('Starting Stock'))
    await user.type(screen.getByLabelText('Starting Stock'), '89')
    await user.type(screen.getByLabelText(/Barcode \/ SKU/), 'YNX-BG66-UM')
  }

  it('validates required fields before sending anything', async () => {
    asUser(manager)
    const posts = vi.fn()
    server.use(http.post(api('/products/'), () => (posts(), HttpResponse.json({}))))
    const { user } = renderApp('/inventory/new')

    await user.click(await screen.findByRole('button', { name: 'Save product' }))

    expect(screen.getByText('Enter a product name.')).toBeInTheDocument()
    expect(screen.getByText('Choose a category.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Selling Price/)).toHaveAttribute('aria-invalid', 'true')
    expect(posts).not.toHaveBeenCalled()
  })

  it('creates the product with starting stock, confirms and returns to the list', async () => {
    asUser(manager)
    let body: Record<string, unknown> = {}
    server.use(
      http.post(api('/products/'), async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeProduct({ name: 'BG66 Ultimax', stock_quantity: 89 }), { status: 201 })
      }),
      http.get(api('/products/'), () => HttpResponse.json({ count: 0, next: null, previous: null, results: [] })),
    )
    const { user, currentPath } = renderApp('/inventory/new')
    expect(await screen.findByRole('heading', { level: 1, name: 'Add Product' })).toBeInTheDocument()
    expect(screen.getByText('Create a product record with price, cost and stock')).toBeInTheDocument()

    await fillRequired(user)
    await user.click(screen.getByRole('button', { name: 'Save product' }))

    expect(await screen.findByText('BG66 Ultimax saved with 89 in stock.')).toBeInTheDocument()
    await waitFor(() => expect(currentPath()).toBe('/inventory'))
    expect(body).toMatchObject({
      name: 'BG66 Ultimax',
      category: 'ACCESSORIES',
      subcategory: 'String',
      cost_price: '320.00',
      selling_price: '450.00',
      initial_stock: 89,
      sku: 'YNX-BG66-UM',
      is_active: true,
    })
  })

  it('shows server field errors next to the field', async () => {
    asUser(manager)
    server.use(
      http.post(api('/products/'), () =>
        HttpResponse.json({ sku: ['A product with this SKU already exists.'] }, { status: 400 }),
      ),
    )
    const { user } = renderApp('/inventory/new')
    await fillRequired(user)
    await user.click(screen.getByRole('button', { name: 'Save product' }))

    expect(await screen.findByText('A product with this SKU already exists.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Barcode \/ SKU/)).toHaveAttribute('aria-invalid', 'true')
  })

  it('shows a starting-stock error from the server next to the stock field', async () => {
    asUser(manager)
    server.use(
      http.post(api('/products/'), () =>
        HttpResponse.json({ initial_stock: ['Ensure this value is greater than or equal to 0.'] }, { status: 400 }),
      ),
    )
    const { user } = renderApp('/inventory/new')
    await fillRequired(user)
    await user.click(screen.getByRole('button', { name: 'Save product' }))

    expect(await screen.findByText('Ensure this value is greater than or equal to 0.')).toBeInTheDocument()
    expect(screen.getByLabelText('Starting Stock')).toHaveAttribute('aria-invalid', 'true')
  })

  it('hides cost from staff without the permission and does not send it', async () => {
    asUser()
    let body: Record<string, unknown> = {}
    server.use(
      http.post(api('/products/'), async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeProduct(), { status: 201 })
      }),
    )
    const { user } = renderApp('/inventory/new')
    await screen.findByLabelText(/Product Name/)
    expect(screen.queryByLabelText(/Cost of Sale/)).not.toBeInTheDocument()

    await fillRequired(user, { cost: false })
    await user.click(screen.getByRole('button', { name: 'Save product' }))
    await waitFor(() => expect(body).toHaveProperty('name'))
    expect(body).not.toHaveProperty('cost_price')
  })

  it('has no accessibility violations', async () => {
    asUser(manager)
    const { container } = renderApp('/inventory/new')
    await screen.findByLabelText(/Product Name/)
    await expectNoAxeViolations(container)
  })
})

describe('Edit Product', () => {
  const product = makeProductDetail({ id: 7, name: 'BG66 Ultimax', selling_price: '450.00', stock_quantity: 89, cost_price: '320.00' })

  function serveProduct(detail = product) {
    server.use(http.get(api('/products/7/'), () => HttpResponse.json(detail)))
  }

  it('prefills the form and shows who last updated it', async () => {
    asUser(manager)
    serveProduct()
    renderApp('/inventory/7/edit')

    expect(await screen.findByRole('heading', { level: 1, name: 'Edit Product' })).toBeInTheDocument()
    expect(await screen.findByLabelText(/Product Name/)).toHaveValue('BG66 Ultimax')
    expect(screen.getByLabelText(/Selling Price/)).toHaveValue('450.00')
    expect(screen.getByText('Last updated 11/18/2026 by Maria Reyes')).toBeInTheDocument()
    expect(screen.getByText('Active')).toHaveClass('ar-badge--navy')
  })

  it('keeps Save disabled until something changes, and requires a reason', async () => {
    asUser(manager)
    serveProduct()
    const patches = vi.fn()
    server.use(http.patch(api('/products/7/'), () => (patches(), HttpResponse.json(product))))
    const { user } = renderApp('/inventory/7/edit')

    const save = await screen.findByRole('button', { name: 'Save changes' })
    expect(save).toBeDisabled()

    await user.clear(screen.getByLabelText(/Selling Price/))
    await user.type(screen.getByLabelText(/Selling Price/), '480')
    expect(save).toBeEnabled()
    await user.click(save)

    expect(screen.getByText('Explain why these details are being updated.')).toBeInTheDocument()
    expect(patches).not.toHaveBeenCalled()
  })

  it('sends only changed fields with their original values', async () => {
    asUser(manager)
    serveProduct()
    let body: unknown
    server.use(
      http.patch(api('/products/7/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...product, selling_price: '480.00', stock_quantity: 85 })
      }),
    )
    const { user, currentPath } = renderApp('/inventory/7/edit')

    await user.clear(await screen.findByLabelText(/Selling Price/))
    await user.type(screen.getByLabelText(/Selling Price/), '480')
    await user.clear(screen.getByLabelText('Stock Quantity'))
    await user.type(screen.getByLabelText('Stock Quantity'), '85')
    await user.type(screen.getByLabelText(/Reason for change/), 'Supplier price increase; recount')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('BG66 Ultimax updated.')).toBeInTheDocument()
    await waitFor(() => expect(currentPath()).toBe('/inventory'))
    expect(body).toEqual({
      changes: { selling_price: '480.00', stock_quantity: 85 },
      expected: { selling_price: '450.00', stock_quantity: 89 },
      reason: 'Supplier price increase; recount',
    })
  })

  it('shows the active state read-only, pointing to Remove/Reactivate', async () => {
    asUser(manager)
    serveProduct()
    renderApp('/inventory/7/edit')

    expect(await screen.findByLabelText('Product is active and sellable')).toBeDisabled()
    expect(screen.getByText(/Use Remove or Reactivate in the product list/)).toBeInTheDocument()
  })

  it('shows server errors that have no matching field instead of failing silently', async () => {
    asUser(manager)
    serveProduct()
    server.use(http.patch(api('/products/7/'), () => HttpResponse.json({ changes: ['Nothing changed.'] }, { status: 400 })))
    const { user } = renderApp('/inventory/7/edit')

    await user.type(await screen.findByLabelText('Supplier'), 'X')
    await user.type(screen.getByLabelText(/Reason for change/), 'Update')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Nothing changed.')
  })

  it('makes stock read-only without the adjust-stock permission', async () => {
    asUser({ ...staffUser, permissions: ['catalog.view_product_cost'] })
    serveProduct()
    renderApp('/inventory/7/edit')

    expect(await screen.findByLabelText('Stock Quantity')).toHaveAttribute('readonly')
    expect(screen.getByText('Ask a manager to adjust stock.')).toBeInTheDocument()
  })

  it('explains a conflict with the current values and keeps the input', async () => {
    asUser(manager)
    serveProduct()
    server.use(
      http.patch(api('/products/7/'), () =>
        HttpResponse.json(
          { detail: 'This product was changed by someone else.', current: { selling_price: '470.00' } },
          { status: 409 },
        ),
      ),
    )
    const { user } = renderApp('/inventory/7/edit')

    await user.clear(await screen.findByLabelText(/Selling Price/))
    await user.type(screen.getByLabelText(/Selling Price/), '480')
    await user.type(screen.getByLabelText(/Reason for change/), 'Reprice')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('changed by someone else')
    expect(alert).toHaveTextContent('Selling Price is now 470.00')
    expect(screen.getByLabelText(/Selling Price/)).toHaveValue('480')
  })

  it('shows a permission error as an alert', async () => {
    asUser(manager)
    serveProduct()
    server.use(http.patch(api('/products/7/'), () => HttpResponse.json({ detail: 'no' }, { status: 403 })))
    const { user } = renderApp('/inventory/7/edit')

    await user.type(await screen.findByLabelText('Supplier'), 'X')
    await user.type(screen.getByLabelText(/Reason for change/), 'Update')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("You don't have permission to do that.")
  })

  it('has no accessibility violations', async () => {
    asUser(manager)
    serveProduct()
    const { container } = renderApp('/inventory/7/edit')
    await screen.findByLabelText(/Product Name/)
    await expectNoAxeViolations(container)
  })
})
