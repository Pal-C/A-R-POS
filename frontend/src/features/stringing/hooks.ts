import { keepPreviousData, useQuery, type QueryClient } from '@tanstack/react-query'
import { customerKeys } from '../../api/customers'
import { stringingApi, stringingKeys, type StringingOrderListParams } from '../../api/stringing'

export const STRINGING_PAGE_SIZE = 20

export function useStringingOrders(params: StringingOrderListParams) {
  return useQuery({ queryKey: stringingKeys.list(params), queryFn: () => stringingApi.list(params), placeholderData: keepPreviousData })
}

/** Chip counts for the list's search and filters (status is ignored by the server). */
export function useStatusCounts(params: Omit<StringingOrderListParams, 'status' | 'page'>) {
  return useQuery({ queryKey: stringingKeys.counts(params), queryFn: () => stringingApi.statusCounts(params), placeholderData: keepPreviousData })
}

export function useStringingOrder(id: number) {
  return useQuery({ queryKey: stringingKeys.detail(id), queryFn: () => stringingApi.get(id), enabled: Number.isInteger(id) && id > 0 })
}

export function useOrderPayments(id: number) {
  return useQuery({ queryKey: stringingKeys.payments(id), queryFn: () => stringingApi.payments(id) })
}

/** Everything an order change can affect: orders, counts, payments and customer summaries. */
export function invalidateAfterStringing(queryClient: QueryClient): Promise<void> {
  return Promise.all([stringingKeys.all, customerKeys.all].map((queryKey) => queryClient.invalidateQueries({ queryKey }))).then(() => undefined)
}
