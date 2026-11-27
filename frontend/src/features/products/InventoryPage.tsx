import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { productsApi, type Product } from '../../api/catalog'
import { toApiError, type ApiError } from '../../api/errors'
import { inventoryApi } from '../../api/inventory'
import { useToast } from '../../components/ui/useToast'
import { formatCount } from '../../lib/format'
import { splitApiError } from './errorDisplay'
import { invalidateProducts } from './hooks'
import { ProductsPage, type ProductDialog } from './ProductsPage'
import { ReactivateProductDialog } from './ReactivateProductDialog'
import { ReceiveStockDialog, type ReceiveStockValues } from './ReceiveStockDialog'
import { RemoveProductDialog } from './RemoveProductDialog'

/** The sidebar's Inventory area: the Products screen plus its dialogs. */
export function InventoryPage() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [dialog, setDialog] = useState<ProductDialog | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  const open = (next: ProductDialog) => {
    setError(null)
    setDialog(next)
  }
  const close = () => setDialog(null)
  const done = async (message: string) => {
    await invalidateProducts(queryClient)
    toast.success(message)
    setDialog(null)
  }
  const fail = (e: unknown) => setError(toApiError(e))

  const remove = useMutation({
    mutationFn: ({ product, reason }: { product: Product; reason: string }) => productsApi.deactivate(product.id, reason),
    onSuccess: (result) => done(`${result.product.name} was removed from sale.`),
    onError: fail,
  })
  const reactivate = useMutation({
    mutationFn: ({ product, reason }: { product: Product; reason: string }) => productsApi.reactivate(product.id, reason),
    onSuccess: (result) => done(`${result.product.name} is active again.`),
    onError: fail,
  })
  const receive = useMutation({
    mutationFn: ({ product, quantity, referenceNumber }: ReceiveStockValues) =>
      inventoryApi.restock({ product_id: product.id, quantity_received: quantity, reference_number: referenceNumber }),
    onSuccess: (movement, { quantity }) =>
      done(`Received ${formatCount(quantity)} × ${movement.product_name}. Stock is now ${formatCount(movement.quantity_after)}.`),
    onError: fail,
  })

  // Remove/Reactivate show every error in their alert; Receive Stock maps its own fields.
  const reasonDialogError = error ? splitApiError(error, []).alert : null
  const receiveError = error ? splitApiError(error, ['quantity_received', 'reference_number']) : null

  return (
    <>
      <ProductsPage onOpenDialog={open} />
      {dialog?.kind === 'remove' && (
        <RemoveProductDialog
          product={dialog.product}
          busy={remove.isPending}
          error={reasonDialogError}
          onClose={close}
          onConfirm={(reason) => remove.mutate({ product: dialog.product, reason })}
        />
      )}
      {dialog?.kind === 'reactivate' && (
        <ReactivateProductDialog
          product={dialog.product}
          busy={reactivate.isPending}
          error={reasonDialogError}
          onClose={close}
          onConfirm={(reason) => reactivate.mutate({ product: dialog.product, reason })}
        />
      )}
      {dialog?.kind === 'receive' && (
        <ReceiveStockDialog
          product={dialog.product}
          busy={receive.isPending}
          error={receiveError?.alert}
          serverErrors={receiveError?.fieldErrors}
          onClose={close}
          onConfirm={(values) => receive.mutate(values)}
        />
      )}
    </>
  )
}
