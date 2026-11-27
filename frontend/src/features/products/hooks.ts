import { keepPreviousData, useQuery, type QueryClient } from '@tanstack/react-query'
import { productKeys, productsApi, type ProductListParams } from '../../api/catalog'
import { inventoryApi, inventoryKeys } from '../../api/inventory'

export const PRODUCTS_PAGE_SIZE = 20

export function useProducts(params: ProductListParams) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => productsApi.list(params),
    placeholderData: keepPreviousData,
  })
}

export function useProduct(id: number | undefined) {
  return useQuery({
    queryKey: productKeys.detail(id ?? 0),
    queryFn: () => productsApi.get(id!),
    enabled: id !== undefined,
  })
}

export function useInventorySummary() {
  return useQuery({ queryKey: inventoryKeys.summary(), queryFn: inventoryApi.summary })
}

/** Refreshes everything a product or stock change can affect. */
export function invalidateProducts(queryClient: QueryClient): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: productKeys.all }),
    queryClient.invalidateQueries({ queryKey: inventoryKeys.all }),
  ]).then(() => undefined)
}
