import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../../api/errors'
import { pageWindow } from '../../lib/pageWindow'
import { expectNoAxeViolations } from '../../test/axe'
import { DataTable, type Column } from './DataTable'
import { Pagination } from './Pagination'

interface Row {
  id: number
  name: string
}
const columns: Column<Row>[] = [{ key: 'name', header: 'Product', render: (r) => r.name }]

describe('DataTable', () => {
  it('renders rows and row actions', async () => {
    const { container } = render(
      <DataTable
        caption="Products"
        columns={columns}
        rows={[{ id: 1, name: 'BG66 Ultimax' }]}
        rowKey={(r) => r.id}
        rowActions={(r) => <button>Edit {r.name}</button>}
        isPending={false}
        error={null}
        empty={<p>No products yet</p>}
      />,
    )
    const table = screen.getByRole('table', { name: 'Products' })
    expect(within(table).getByRole('columnheader', { name: 'Product' })).toBeInTheDocument()
    expect(within(table).getByRole('cell', { name: 'BG66 Ultimax' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit BG66 Ultimax' })).toBeInTheDocument()
    await expectNoAxeViolations(container)
  })

  it('shows loading, error and empty states', () => {
    const base = { caption: 'Products', columns, rowKey: (r: Row) => r.id, empty: <p>No products yet</p> }
    const { rerender } = render(<DataTable {...base} rows={undefined} isPending error={null} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading')

    rerender(<DataTable {...base} rows={undefined} isPending={false} error={new ApiError({ kind: 'network', status: null, message: 'Cannot reach the server.' })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach the server.')

    rerender(<DataTable {...base} rows={[]} isPending={false} error={null} />)
    expect(screen.getByText('No products yet')).toBeInTheDocument()
  })

  it('keeps showing previous rows while the next page loads', () => {
    render(
      <DataTable caption="Products" columns={columns} rows={[{ id: 1, name: 'Kept' }]} rowKey={(r) => r.id} isPending error={null} empty={null} />,
    )
    expect(screen.getByText('Kept')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('Pagination', () => {
  it('summarizes the range and marks the current page', async () => {
    const onPageChange = vi.fn()
    const { container } = render(<Pagination page={2} pageSize={20} count={45} onPageChange={onPageChange} noun="products" />)
    expect(screen.getByText('Showing 21–40 of 45 products')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Page 2' })).toHaveAttribute('aria-current', 'page')
    await userEvent.click(screen.getByRole('button', { name: 'Page 3' }))
    expect(onPageChange).toHaveBeenCalledWith(3)
    await expectNoAxeViolations(container)
  })

  it('handles the last partial page and a single page', () => {
    const { rerender } = render(<Pagination page={3} pageSize={20} count={45} onPageChange={() => {}} noun="products" />)
    expect(screen.getByText('Showing 41–45 of 45 products')).toBeInTheDocument()
    rerender(<Pagination page={1} pageSize={20} count={0} onPageChange={() => {}} noun="products" />)
    expect(screen.getByText('Showing 0–0 of 0 products')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('collapses long page lists with gaps', () => {
    expect(pageWindow(5, 10)).toEqual([1, 'gap', 4, 5, 6, 'gap', 10])
    expect(pageWindow(1, 3)).toEqual([1, 2, 3])
  })
})
