import type { Product, ProductDetail } from '../api/catalog'
import type { Paginated } from '../api/client'

let nextId = 1

export function makeProduct(overrides: Partial<Product> = {}): Product {
  const id = overrides.id ?? nextId++
  return {
    id,
    sku: `SKU-${id}`,
    name: `Product ${id}`,
    category: 'ACCESSORIES',
    subcategory: 'String',
    brand: 'Yonex',
    variant_description: '',
    model: '',
    supplier: '',
    description: '',
    selling_price: '450.00',
    cost_price: '320.00',
    stock_quantity: 89,
    low_stock_threshold: 5,
    is_low_stock: false,
    is_out_of_stock: false,
    stock_status: 'IN_STOCK',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-18T08:10:00Z',
    ...overrides,
  }
}

export function makeProductDetail(overrides: Partial<ProductDetail> = {}): ProductDetail {
  return {
    ...makeProduct(overrides),
    last_event: {
      action: 'UPDATED',
      performed_by: { id: 3, username: 'maria', display_name: 'Maria Reyes' },
      created_at: '2026-11-18T08:10:00Z',
    },
    ...overrides,
  }
}

export function page<T>(results: T[], count = results.length): Paginated<T> {
  return { count, next: null, previous: null, results }
}
