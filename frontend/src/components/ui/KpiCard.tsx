import { cx } from '../../lib/cx'

export interface KpiCardProps {
  label: string
  value: string
  caption: string
  /** Navy card with a yellow value (e.g. Low Stock). */
  highlight?: boolean
  isPending?: boolean
}

export function KpiCard({ label, value, caption, highlight = false, isPending = false }: KpiCardProps) {
  return (
    <section className={cx('ar-kpi', highlight && 'ar-kpi--highlight')} aria-label={label}>
      <h2 className="ar-kpi__label">{label}</h2>
      <p className="ar-kpi__value" aria-busy={isPending || undefined}>
        {isPending ? <span className="placeholder col-4" aria-label="Loading" /> : value}
      </p>
      <p className="ar-kpi__caption">{caption}</p>
    </section>
  )
}
