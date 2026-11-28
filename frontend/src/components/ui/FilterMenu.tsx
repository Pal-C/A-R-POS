import { Funnel } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { SelectField, TextField, type SelectOption } from './fields'

export interface FilterDefinition {
  name: string
  label: string
  /** `select` (default) uses `options`; `date` is a YYYY-MM-DD date input. */
  type?: 'select' | 'date'
  options?: SelectOption[]
  /** Value used when nothing is chosen; when set, the filter has no "All" choice. */
  defaultValue?: string
}

export interface FilterMenuProps {
  filters: FilterDefinition[]
  values: Record<string, string>
  onChange: (name: string, value: string) => void
  onClear: () => void
}

/** The outlined FILTER button with a panel of filters; changes apply immediately. */
export function FilterMenu({ filters, values, onChange, onClear }: FilterMenuProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const isActive = (f: FilterDefinition) => !!values[f.name] && values[f.name] !== (f.defaultValue ?? '')
  const activeCount = filters.filter(isActive).length

  useEffect(() => {
    if (!open) return
    const onDocumentClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocumentClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocumentClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="ar-filter" ref={rootRef}>
      <button
        type="button"
        className="btn ar-btn ar-btn--secondary"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <Funnel size={18} aria-hidden="true" />
        <span>Filter</span>
        {activeCount > 0 && (
          <span className="ar-filter__count" aria-label={`${activeCount} active`}>
            {activeCount}
          </span>
        )}
      </button>
      {open && (
        <div id={panelId} className="ar-filter__panel" role="group" aria-label="Filters">
          {filters.map((filter) =>
            filter.type === 'date' ? (
              <TextField
                key={filter.name}
                type="date"
                label={filter.label}
                name={`filter-${filter.name}`}
                value={values[filter.name] || ''}
                onChange={(value) => onChange(filter.name, value)}
              />
            ) : (
              <SelectField
                key={filter.name}
                label={filter.label}
                name={`filter-${filter.name}`}
                value={values[filter.name] || filter.defaultValue || ''}
                onChange={(value) => onChange(filter.name, value)}
                options={filter.options ?? []}
                placeholder={filter.defaultValue === undefined ? 'All' : undefined}
              />
            ),
          )}
          <button type="button" className="btn btn-link px-0" onClick={onClear} disabled={activeCount === 0}>
            Clear filters
          </button>
        </div>
      )}
    </div>
  )
}
