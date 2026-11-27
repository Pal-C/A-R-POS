import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expectNoAxeViolations } from '../../test/axe'
import { makeSale, page } from '../../test/fixtures'
import { api, asUser } from '../../test/handlers'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const completed = makeSale({ id: 142, payment_methods: ['CASH', 'GCASH'] })
const draft = makeSale({ id: 150, status: 'DRAFT', sale_number: null, sale_date: null, payment_methods: [], customer: null, customer_name: null })

function serveSales(onRequest?: (url: URL) => void, results = [draft, completed], count?: number) {
  server.use(
    http.get(api('/sales/'), ({ request }) => {
      onRequest?.(new URL(request.url))
      return HttpResponse.json(page(results, count))
    }),
  )
}

describe('Sales list', () => {
  it('shows number, products, customer, total, methods, date and status', async () => {
    asUser()
    serveSales()
    renderApp('/sales')

    const table = await screen.findByRole('table', { name: 'Sales' })
    const row = (await within(table).findByRole('link', { name: 'S20261127-000142' })).closest('tr')!
    expect(row).toHaveTextContent('BG66 Ultimax ×1, Super Grap ×2')
    expect(within(row).getByText('BG66 Ultimax ×1, Super Grap ×2')).toHaveAttribute('title', 'BG66 Ultimax ×1, Super Grap ×2')
    expect(row).toHaveTextContent('Juan Dela Cruz')
    expect(row).toHaveTextContent('₱650.00')
    expect(row).toHaveTextContent('Cash, GCash')
    expect(row).toHaveTextContent('11/27/2026')
    expect(within(row).getByText('Completed')).toHaveClass('ar-badge--navy')

    const draftRow = within(table).getByRole('link', { name: 'Draft #150' }).closest('tr')!
    expect(draftRow).toHaveTextContent('Walk-in')
    expect(within(draftRow).getByText('Draft')).toBeInTheDocument()
  })

  it('searches and filters through the URL, and pages', async () => {
    asUser()
    const urls: URL[] = []
    serveSales((url) => urls.push(url), [completed], 25)
    const { user, currentPath } = renderApp('/sales')
    await screen.findByRole('link', { name: 'S20261127-000142' })

    await user.type(screen.getByLabelText('Search by sale number or customer'), 'juan')
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('search')).toBe('juan'))
    await user.click(screen.getByRole('button', { name: /filter/i }))
    await user.selectOptions(screen.getByLabelText('Status'), 'PENDING_PAYMENT')
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('status')).toBe('PENDING_PAYMENT'))
    expect(currentPath()).toBe('/sales?search=juan&status=PENDING_PAYMENT')

    await user.click(screen.getByRole('button', { name: 'Page 2' }))
    await waitFor(() => expect(urls.at(-1)!.searchParams.get('page')).toBe('2'))
  })

  it('opens a sale and goes to Create Sale', async () => {
    asUser()
    serveSales()
    server.use(http.get(api('/sales/142/'), () => HttpResponse.json(completed)))
    const { user, currentPath, router } = renderApp('/sales')
    await user.click(await screen.findByRole('link', { name: 'S20261127-000142' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Sale Details' })).toBeInTheDocument()
    expect(currentPath()).toBe('/sales/142')

    await router.navigate('/sales')
    await user.click(await screen.findByRole('button', { name: /create sale/i }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Create Sale' })).toBeInTheDocument()
  })

  it('shows empty and error states', async () => {
    asUser()
    serveSales(undefined, [])
    const { unmount } = renderApp('/sales')
    expect(await screen.findByText('No sales yet.')).toBeInTheDocument()
    unmount()

    server.use(http.get(api('/sales/'), () => HttpResponse.error()))
    renderApp('/sales?status=CANCELLED')
    expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    asUser()
    serveSales()
    const { container } = renderApp('/sales')
    await screen.findByRole('link', { name: 'S20261127-000142' })
    await expectNoAxeViolations(container)
  })
})
