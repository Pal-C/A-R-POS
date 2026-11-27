import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { productsApi } from './catalog'
import { customersApi } from './customers'
import { inventoryApi } from './inventory'
import { preordersApi } from './preorders'
import { salesApi } from './sales'
import { stringingApi } from './stringing'

interface Seen {
  method: string
  path: string
  query: Record<string, string>
  body: unknown
}

let seen: Seen | null = null
const reply = { marker: 'typed-result' }

beforeEach(() => {
  seen = null
  server.use(
    http.all('*/api/*', async ({ request }) => {
      const url = new URL(request.url)
      const text = request.method === 'GET' || request.method === 'DELETE' ? '' : await request.text()
      seen = {
        method: request.method,
        path: url.pathname,
        query: Object.fromEntries(url.searchParams),
        body: text ? JSON.parse(text) : undefined,
      }
      return HttpResponse.json(reply)
    }),
  )
})

type Case = [name: string, call: () => Promise<unknown>, method: string, path: string, query?: Record<string, string>, body?: unknown]

const cases: Case[] = [
  // catalog
  ['products.list', () => productsApi.list({ category: 'RACKET', is_active: true, page: 2 }), 'GET', '/api/products/', { category: 'RACKET', is_active: 'true', page: '2' }],
  ['products.get', () => productsApi.get(5), 'GET', '/api/products/5/'],
  ['products.create', () => productsApi.create({ sku: 'A', name: 'X', category: 'RACKET', selling_price: '1.00', initial_stock: 3 }), 'POST', '/api/products/', {}, { sku: 'A', name: 'X', category: 'RACKET', selling_price: '1.00', initial_stock: 3 }],
  ['products.update', () => productsApi.update(5, { changes: { name: 'X' }, expected: { name: 'W' }, reason: 'Typo' }), 'PATCH', '/api/products/5/', {}, { changes: { name: 'X' }, expected: { name: 'W' }, reason: 'Typo' }],
  ['products.deactivate', () => productsApi.deactivate(5, 'Discontinued'), 'POST', '/api/products/5/deactivate/', {}, { reason: 'Discontinued' }],
  ['products.reactivate', () => productsApi.reactivate(5, 'Back in range'), 'POST', '/api/products/5/reactivate/', {}, { reason: 'Back in range' }],
  ['products.history', () => productsApi.history(5, { page: 2 }), 'GET', '/api/products/5/history/', { page: '2' }],
  // inventory
  ['inventory.movements', () => inventoryApi.movements({ product_id: 3, movement_type: 'RESTOCK' }), 'GET', '/api/inventory/movements/', { product_id: '3', movement_type: 'RESTOCK' }],
  ['inventory.restock', () => inventoryApi.restock({ product_id: 3, quantity_received: 4 }), 'POST', '/api/inventory/restocks/', {}, { product_id: 3, quantity_received: 4 }],
  ['inventory.adjust', () => inventoryApi.adjust({ product_id: 3, quantity_change: -1, reason: 'Damaged' }), 'POST', '/api/inventory/adjustments/'],
  ['inventory.reverse', () => inventoryApi.reverse(9, { reason: 'Wrong entry' }), 'POST', '/api/inventory/movements/9/reverse/'],
  ['inventory.lowStock', () => inventoryApi.lowStock(), 'GET', '/api/inventory/low-stock/'],
  ['inventory.outOfStock', () => inventoryApi.outOfStock(), 'GET', '/api/inventory/out-of-stock/'],
  ['inventory.summary', () => inventoryApi.summary(), 'GET', '/api/inventory/summary/'],
  // sales
  ['sales.list', () => salesApi.list({ status: 'DRAFT', customer_id: 2 }), 'GET', '/api/sales/', { status: 'DRAFT', customer_id: '2' }],
  ['sales.create', () => salesApi.create({ items: [{ product_id: 1, quantity: 2 }] }), 'POST', '/api/sales/', {}, { items: [{ product_id: 1, quantity: 2 }] }],
  ['sales.addItem', () => salesApi.addItem(4, { product_id: 1, quantity: 1 }), 'POST', '/api/sales/4/items/'],
  ['sales.updateItem', () => salesApi.updateItem(4, 8, { quantity: 3 }), 'PATCH', '/api/sales/4/items/8/'],
  ['sales.removeItem', () => salesApi.removeItem(4, 8), 'DELETE', '/api/sales/4/items/8/'],
  ['sales.finalize', () => salesApi.finalize(4), 'POST', '/api/sales/4/finalize/'],
  ['sales.cancel', () => salesApi.cancel(4, { reason: 'Customer left' }), 'POST', '/api/sales/4/cancel/', {}, { reason: 'Customer left' }],
  ['sales.payments', () => salesApi.payments({ sale_id: 4 }), 'GET', '/api/sales/payments/', { sale_id: '4' }],
  ['sales.recordPayment', () => salesApi.recordPayment({ sale: 4, amount: '100.00', payment_method: 'CASH' }), 'POST', '/api/sales/payments/', {}, { sale: 4, amount: '100.00', payment_method: 'CASH' }],
  // customers
  ['customers.list', () => customersApi.list({ status: 'archived', search: 'ana' }), 'GET', '/api/customers/', { status: 'archived', search: 'ana' }],
  ['customers.create', () => customersApi.create({ full_name: 'Ana' }), 'POST', '/api/customers/'],
  ['customers.archive', () => customersApi.archive(12), 'POST', '/api/customers/12/archive/'],
  ['customers.reactivate', () => customersApi.reactivate(12), 'POST', '/api/customers/12/reactivate/'],
  ['customers.remove', () => customersApi.remove(12), 'DELETE', '/api/customers/12/'],
  ['customers.phoneMatches', () => customersApi.phoneMatches('0917', 12), 'GET', '/api/customers/phone-matches/', { phone: '0917', exclude_id: '12' }],
  ['customers.sales', () => customersApi.sales(12), 'GET', '/api/customers/12/sales/'],
  ['customers.stringingOrders', () => customersApi.stringingOrders(12), 'GET', '/api/customers/12/stringing-orders/'],
  ['customers.preorders', () => customersApi.preorders(12, { page: 2 }), 'GET', '/api/customers/12/preorders/', { page: '2' }],
  // stringing
  ['stringing.list', () => stringingApi.list({ status: 'READY,RECEIVED', payment_state: 'UNPAID' }), 'GET', '/api/stringing/orders/', { status: 'READY,RECEIVED', payment_state: 'UNPAID' }],
  ['stringing.get', () => stringingApi.get(41), 'GET', '/api/stringing/orders/41/'],
  ['stringing.changeStatus', () => stringingApi.changeStatus(41, { status: 'READY', expected_status: 'IN_PROGRESS' }), 'POST', '/api/stringing/orders/41/status/'],
  ['stringing.cancel', () => stringingApi.cancel(41, { reason: 'x' }), 'POST', '/api/stringing/orders/41/cancel/'],
  ['stringing.recordPayment', () => stringingApi.recordPayment(41, { payment_type: 'RECEIPT', amount: '200.00', payment_method: 'GCASH' }), 'POST', '/api/stringing/orders/41/payments/'],
  ['stringing.history', () => stringingApi.history(41), 'GET', '/api/stringing/orders/41/history/'],
  ['stringing.revenueReport', () => stringingApi.revenueReport('2026-11-01', '2026-11-30'), 'GET', '/api/stringing/reports/revenue/', { date_from: '2026-11-01', date_to: '2026-11-30' }],
  // preorders
  ['preorders.list', () => preordersApi.list({ overdue: true, product: 3 }), 'GET', '/api/preorders/', { overdue: 'true', product: '3' }],
  ['preorders.create', () => preordersApi.create({ customer: 12, product: 3, quantity: 2 }), 'POST', '/api/preorders/'],
  ['preorders.update', () => preordersApi.update(7, { quantity: 3 }), 'PATCH', '/api/preorders/7/'],
  ['preorders.changeStatus', () => preordersApi.changeStatus(7, { status: 'ORDERED' }), 'POST', '/api/preorders/7/status/'],
  ['preorders.fulfill', () => preordersApi.fulfill(7), 'POST', '/api/preorders/7/fulfill/'],
  ['preorders.cancel', () => preordersApi.cancel(7, { reason: 'Discontinued' }), 'POST', '/api/preorders/7/cancel/'],
  ['preorders.payments', () => preordersApi.payments(7), 'GET', '/api/preorders/7/payments/'],
  ['preorders.history', () => preordersApi.history(7), 'GET', '/api/preorders/7/history/'],
  ['preorders.productSummary', () => preordersApi.productSummary(3), 'GET', '/api/preorders/products/3/summary/'],
  ['preorders.markArrived', () => preordersApi.markArrived(3, { received_quantity: 3, preorder_ids: [7, 9] }), 'POST', '/api/preorders/products/3/arrivals/', {}, { received_quantity: 3, preorder_ids: [7, 9] }],
]

describe('domain API modules', () => {
  it.each(cases)('%s → %s %s', async (_name, call, method, path, query = {}, body) => {
    const result = await call()

    expect(seen).not.toBeNull()
    expect(seen!.method).toBe(method)
    expect(seen!.path).toBe(path)
    expect(seen!.query).toEqual(query)
    if (body !== undefined) expect(seen!.body).toEqual(body)
    expect(result).toEqual(reply)
  })
})
