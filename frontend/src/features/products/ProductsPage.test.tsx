import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeProduct, makeProductDetail, page } from '../../test/fixtures'
import { api, asUser, staffUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const manager = { ...staffUser, permissions: ['catalog.view_product_cost', 'catalog.adjust_stock'] }

const summary = {
  active_product_count: 42,
  total_units_in_stock: 500,
  low_stock_count: 2,
  out_of_stock_count: 1,
  inventory_value: '186400.00',
}

function serveProducts(onRequest?: (url: URL) => void, results = [
  makeProduct({ name: 'BG66 Ultimax', subcategory: 'String', brand: 'Yonex', selling_price: '450.00', stock_quantity: 89 }),
  makeProduct({ name: 'Astrox 88D Pro', category: 'RACKET', subcategory: '', selling_price: '11500.00', stock_quantity: 3, stock_status: 'LOW_STOCK' }),
  makeProduct({ name: 'Aerosonic', stock_quantity: 0, stock_status: 'OUT_OF_STOCK' }),
], count?: number) {
  server.use(
    http.get(api('/products/'), ({ request }) => {
      onRequest?.(new URL(request.url))
      return HttpResponse.json(page(results, count))
    }),
    http.get(api('/inventory/summary/'), () => HttpResponse.json(summary)),
  )
}

describe('ProductsPage', () => {
  it('shows the KPI cards, including inventory value for managers', async () => {
    asUser(manager)
    serveProducts()
    renderApp('/inventory')

    const total = await screen.findByRole('region', { name: 'Total Products' })
    await waitFor(() => expect(total).toHaveTextContent('42'))
    expect(screen.getByRole('region', { name: 'Low Stock' })).toHaveTextContent('2')
    expect(screen.getByRole('region', { name: 'Low Stock' })).toHaveClass('ar-kpi--highlight')
    expect(screen.getByRole('region', { name: 'Out of Stock' })).toHaveTextContent('1')
    expect(screen.getByRole('region', { name: 'Inventory Value' })).toHaveTextContent('₱186,400')
  })

  it('hides inventory value from staff without the cost permission', async () => {
    asUser()
    serveProducts()
    renderApp('/inventory')

    await screen.findByRole('region', { name: 'Total Products' })
    expect(screen.queryByRole('region', { name: 'Inventory Value' })).not.toBeInTheDocument()
  })

  it('lists products with type, brand, price, stock and status badges', async () => {
    asUser()
    serveProducts()
    renderApp('/inventory')

    const table = await screen.findByRole('table', { name: 'Products' })
    const row = (await within(table).findByText('BG66 Ultimax')).closest('tr')!
    expect(row).toHaveTextContent('String')
    expect(row).toHaveTextContent('Yonex')
    expect(row).toHaveTextContent('₱450')
    expect(row).toHaveTextContent('89')
    expect(within(row).getByText('In Stock')).toHaveClass('ar-badge--outline')

    const racket = within(table).getByText('Astrox 88D Pro').closest('tr')!
    expect(racket).toHaveTextContent('Racket')
    expect(racket).toHaveTextContent('₱11,500')
    expect(within(racket).getByText('Low Stock')).toHaveClass('ar-badge--yellow')
    expect(within(table).getByText('Out of Stock')).toHaveClass('ar-badge--black')
  })

  it('searches after typing pauses and shows active products by default', async () => {
    asUser()
    const urls: URL[] = []
    serveProducts((url) => urls.push(url))
    const { user, currentPath } = renderApp('/inventory')
    await screen.findByText('BG66 Ultimax')
    expect(urls[0]!.searchParams.get('is_active')).toBe('true')

    await user.type(screen.getByLabelText('Search by name, type or brand'), 'BG66')
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('search')).toBe('BG66'))
    expect(currentPath()).toBe('/inventory?search=BG66')
  })

  it('filters by stock status and availability, and clears filters', async () => {
    asUser()
    const urls: URL[] = []
    serveProducts((url) => urls.push(url))
    const { user, currentPath } = renderApp('/inventory')
    await screen.findByText('BG66 Ultimax')

    await user.click(screen.getByRole('button', { name: /filter/i }))
    await user.selectOptions(screen.getByLabelText('Stock status'), 'LOW_STOCK')
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('stock_status')).toBe('LOW_STOCK'))
    await user.selectOptions(screen.getByLabelText('Availability'), 'inactive')
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('is_active')).toBe('false'))
    await user.selectOptions(screen.getByLabelText('Availability'), 'all')
    await waitFor(() => expect(urls.at(-1)!.searchParams.has('is_active')).toBe(false))

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    // The unfiltered list is served from cache, so check the URL rather than a new request.
    expect(currentPath()).toBe('/inventory')
    expect(screen.queryByLabelText(/active$/)).not.toBeInTheDocument()
  })

  it('pages through results', async () => {
    asUser()
    const urls: URL[] = []
    serveProducts((url) => urls.push(url), Array.from({ length: 5 }, (_, i) => makeProduct({ name: `Item ${i}` })), 25)
    const { user } = renderApp('/inventory')
    expect(await screen.findByText('Showing 1–20 of 25 products')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Page 2' }))
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('page')).toBe('2'))
    expect(await screen.findByText('Showing 21–25 of 25 products')).toBeInTheDocument()
  })

  it('shows inactive products with an Inactive badge', async () => {
    asUser()
    serveProducts(undefined, [makeProduct({ name: 'Old Grip', is_active: false })])
    renderApp('/inventory?availability=inactive')
    const row = (await screen.findByText('Old Grip')).closest('tr')!
    expect(within(row).getByText('Inactive')).toHaveClass('ar-badge--muted')
  })

  it('shows an empty catalog state with Add product', async () => {
    asUser()
    serveProducts(undefined, [])
    renderApp('/inventory')
    expect(await screen.findByText('No products yet.')).toBeInTheDocument()
  })

  it('shows a no-match state with Clear filters', async () => {
    asUser()
    serveProducts(undefined, [])
    renderApp('/inventory?search=zzz')
    expect(await screen.findByText('No products match your search or filters.')).toBeInTheDocument()
  })

  it('shows a readable error', async () => {
    asUser()
    server.use(http.get(api('/products/'), () => HttpResponse.error()))
    renderApp('/inventory')
    expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument()
  })

  it('goes to Add Product and Edit Product', async () => {
    asUser()
    serveProducts(undefined, [makeProduct({ id: 7, name: 'BG66 Ultimax' })])
    server.use(http.get(api('/products/7/'), () => HttpResponse.json(makeProductDetail({ id: 7, name: 'BG66 Ultimax' }))))
    const { user, currentPath, router } = renderApp('/inventory')
    await user.click(await screen.findByRole('button', { name: 'Edit BG66 Ultimax' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Edit Product' })).toBeInTheDocument()
    expect(currentPath()).toBe('/inventory/7/edit')
    await router.navigate('/inventory')
    await user.click(await screen.findByRole('button', { name: /add product/i }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Add Product' })).toBeInTheDocument()
    expect(currentPath()).toBe('/inventory/new')
  })

  it('has no accessibility violations', async () => {
    asUser(manager)
    serveProducts()
    const { container } = renderApp('/inventory')
    await screen.findByText('BG66 Ultimax')
    await expectNoAxeViolations(container)
  })
})
