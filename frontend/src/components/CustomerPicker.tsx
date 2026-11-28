import { useMutation, useQuery } from '@tanstack/react-query'
import { UserPlus, Users, X } from 'lucide-react'
import { useId, useState } from 'react'
import { customerKeys, customersApi } from '../../api/customers'
import { toApiError, type FieldErrors } from '../../api/errors'
import { Button } from '../../components/ui/Button'
import { TextField } from '../../components/ui/fields'
import { SearchBox } from '../../components/ui/SearchBox'
import type { CartCustomer } from './cartReducer'

export interface CustomerPickerProps {
  value: CartCustomer | null
  onChange: (customer: CartCustomer | null) => void
  /** Allow clearing back to a walk-in sale. */
  allowWalkIn?: boolean
}

/** Find a customer by name or phone, create one inline, or leave the sale as walk-in. */
export function CustomerPicker({ value, onChange, allowWalkIn = true }: CustomerPickerProps) {
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const resultsId = useId()

  const params = { search, status: 'active' as const }
  const results = useQuery({
    queryKey: customerKeys.list(params),
    queryFn: () => customersApi.list(params),
    enabled: search.trim().length > 0 && !value,
  })
  const create = useMutation({
    mutationFn: () => customersApi.create({ full_name: name.trim(), phone_number: phone.trim() }),
    onSuccess: (customer) => {
      onChange({ id: customer.id, full_name: customer.full_name, phone_number: customer.phone_number })
      setCreating(false)
      setName('')
      setPhone('')
    },
    onError: (error) => setErrors(toApiError(error).fieldErrors),
  })

  if (value) {
    return (
      <div className="ar-customer-chip" role="group" aria-label="Customer">
        <Users size={20} aria-hidden="true" />
        <div>
          <p className="mb-0 fw-semibold">{value.full_name}</p>
          <p className="mb-0 text-body-secondary small">{value.phone_number || 'No contact number'}</p>
        </div>
        {allowWalkIn && (
          <button type="button" className="ar-customer-chip__clear" aria-label={`Remove ${value.full_name}`} onClick={() => onChange(null)}>
            <X size={18} aria-hidden="true" />
          </button>
        )}
      </div>
    )
  }

  if (creating) {
    return (
      <div className="ar-customer-new" role="group" aria-label="New customer">
        <TextField label="Customer Name" name="new_customer_name" value={name} onChange={setName} error={errors.full_name} required />
        <TextField label="Customer Contact #" name="new_customer_phone" type="tel" value={phone} onChange={setPhone} error={errors.phone_number} placeholder="09XX XXX XXXX" />
        <div className="d-flex gap-2">
          <Button size="sm" busy={create.isPending} onClick={() => (name.trim() ? create.mutate() : setErrors({ full_name: ['Enter the customer name.'] }))}>
            Save customer
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setCreating(false)}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  const matches = results.data?.results ?? []
  return (
    <div className="ar-customer-picker">
      <SearchBox value={search} onChange={setSearch} placeholder="Find customer by name or phone" label="Customer" />
      {search.trim() && (
        <ul id={resultsId} className="ar-customer-results" aria-label="Matching customers">
          {results.isPending && <li className="text-body-secondary">Searching…</li>}
          {!results.isPending && matches.length === 0 && <li className="text-body-secondary">No customers match.</li>}
          {matches.map((customer) => (
            <li key={customer.id}>
              <button
                type="button"
                className="ar-customer-results__item"
                onClick={() => {
                  onChange({ id: customer.id, full_name: customer.full_name, phone_number: customer.phone_number })
                  setSearch('')
                }}
              >
                <span className="fw-semibold">{customer.full_name}</span>
                <span className="text-body-secondary small">{customer.phone_number}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Button variant="ghost" size="sm" icon={UserPlus} onClick={() => setCreating(true)}>
        New customer
      </Button>
    </div>
  )
}
