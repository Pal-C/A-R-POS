import { cx } from '../../lib/cx'
import { formatCount } from '../../lib/format'
import { pageWindow } from '../../lib/pageWindow'

export interface PaginationProps {
  page: number
  pageSize: number
  count: number
  onPageChange: (page: number) => void
  /** Plural noun for the summary, e.g. "products". */
  noun: string
}

export function Pagination({ page, pageSize, count, onPageChange, noun }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize))
  const first = count === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, count)
  return (
    <div className="ar-pagination">
      <p className="ar-pagination__summary mb-0" aria-live="polite">
        Showing {formatCount(first)}–{formatCount(last)} of {formatCount(count)} {noun}
      </p>
      {totalPages > 1 && (
        <nav aria-label="Pagination">
          <ul className="ar-pagination__pages">
            {pageWindow(page, totalPages).map((p, i) =>
              p === 'gap' ? (
                <li key={`gap-${i}`} aria-hidden="true" className="ar-pagination__gap">
                  …
                </li>
              ) : (
                <li key={p}>
                  <button
                    type="button"
                    className={cx('ar-pagination__page', p === page && 'is-current')}
                    aria-current={p === page ? 'page' : undefined}
                    aria-label={`Page ${p}`}
                    onClick={() => onPageChange(p)}
                  >
                    {p}
                  </button>
                </li>
              ),
            )}
          </ul>
        </nav>
      )}
    </div>
  )
}
