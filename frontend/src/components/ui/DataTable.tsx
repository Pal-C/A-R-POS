import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { QueryState } from '../QueryState'

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  /** CSS width, e.g. "30%". */
  width?: string
  align?: 'start' | 'end' | 'center'
  className?: string
}

export interface DataTableProps<T> {
  caption: string
  columns: Column<T>[]
  rows: T[] | undefined
  rowKey: (row: T) => string | number
  rowActions?: (row: T) => ReactNode
  isPending: boolean
  error: unknown
  /** Shown when the request succeeded with no rows. */
  empty: ReactNode
}

/** The light-blue-header table from the references, with built-in loading/error/empty states. */
export function DataTable<T>({ caption, columns, rows, rowKey, rowActions, isPending, error, empty }: DataTableProps<T>) {
  const isEmpty = !isPending && !error && (rows?.length ?? 0) === 0
  return (
    <div className="ar-table">
      <table className="table mb-0">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={cx(column.align && `text-${column.align}`)}
              >
                {column.header}
              </th>
            ))}
            {rowActions && (
              <th scope="col" className="ar-table__actions-head">
                <span className="visually-hidden">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        {rows && rows.length > 0 && !error && (
          <tbody>
            {rows.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((column) => (
                  <td key={column.key} className={cx(column.align && `text-${column.align}`, column.className)}>
                    {column.render(row)}
                  </td>
                ))}
                {rowActions && <td className="ar-table__actions">{rowActions(row)}</td>}
              </tr>
            ))}
          </tbody>
        )}
      </table>
      {(isPending || !!error || isEmpty) && (
        <div className="ar-table__state">
          <QueryState isPending={isPending && !rows} error={error} isEmpty={isEmpty} emptyText="">
            {null}
          </QueryState>
          {isEmpty && empty}
        </div>
      )}
    </div>
  )
}
