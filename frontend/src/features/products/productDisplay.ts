import { PRODUCT_CATEGORIES, type Product } from '../../api/catalog'

export function categoryLabel(category: string): string {
  return PRODUCT_CATEGORIES.find((c) => c.value === category)?.label ?? category
}

/** The "Type" column: subcategory when set (e.g. "String"), otherwise the category. */
export function productType(product: Pick<Product, 'category' | 'subcategory'>): string {
  return product.subcategory.trim() || categoryLabel(product.category)
}
