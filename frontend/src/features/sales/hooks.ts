import { keepPreviousData, useQuery, type QueryClient } from '@tanstack/react-query'
import { productKeys } from '../../api/catalog'
import { customerKeys } from '../../api/customers'
import { inventoryKeys } from '../../api/inventory'
import { saleKeys, salesApi, type SaleListParams } from '../../api/sales'

export const SALES_PAGE_SIZE = 20

export function useSales(params: SaleListParams) {
  return useQuery({ queryKey: saleKeys.list(params), queryFn: () => salesApi.list(params), placeholderData: keepPreviousData })
}

export function useSale(id: number) {
  return useQuery({ queryKey: saleKeys.detail(id), queryFn: () => salesApi.get(id) })
}

/** Everything a sale change can affect: sales, stock levels, customer summaries. */
export function invalidateAfterSale(queryClient: QueryClient): Promise<void> {
  return Promise.all(
    [saleKeys.all, productKeys.all, inventoryKeys.all, customerKeys.all].map((queryKey) =>
      queryClient.invalidateQueries({ queryKey }),
    ),
  ).then(() => undefined)
}
