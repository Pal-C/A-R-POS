import { cx } from '../../lib/cx'

export interface StatusChipItem {
  value: string
  label: string
  count?: number
}

/** Pill chips for filtering by status ("All 28", "Received 5", …). */
export function StatusChips({ items, value, onChange, label = 'Filter by status' }: { items: StatusChipItem[]; value: string; onChange: (value: string) => void; label?: string }) {
  return (
    <div className="ar-chips" role="group" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          className={cx('ar-chip', item.value === value && 'ar-chip--selected')}
          aria-pressed={item.value === value}
          onClick={() => onChange(item.value)}
        >
          {item.label}
          {item.count !== undefined && (
            <>
              {' '}
              <span className="ar-chip__count">{item.count}</span>
            </>
          )}
        </button>
      ))}
    </div>
  )
}
