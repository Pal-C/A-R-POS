import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expectNoAxeViolations } from '../../test/axe'
import { FilterMenu } from './FilterMenu'
import { SearchBox } from './SearchBox'
import { StatusChips } from './StatusChips'

describe('SearchBox', () => {
  afterEach(() => vi.useRealTimers())

  it('reports the value after the debounce only', () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<SearchBox value="" onChange={onChange} placeholder="Search by name, type or brand" />)
    const input = screen.getByLabelText('Search by name, type or brand')
    fireEvent.change(input, { target: { value: 'BG' } })
    fireEvent.change(input, { target: { value: 'BG66' } })
    expect(onChange).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(250))
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('BG66')
  })

  it('clears immediately with the clear button', async () => {
    const onChange = vi.fn()
    render(<SearchBox value="BG66" onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Clear search' }))
    expect(onChange).toHaveBeenCalledWith('')
    expect(screen.getByRole('searchbox')).toHaveValue('')
  })

  it('follows external resets', () => {
    const { rerender } = render(<SearchBox value="abc" onChange={() => {}} />)
    rerender(<SearchBox value="" onChange={() => {}} />)
    expect(screen.getByRole('searchbox')).toHaveValue('')
  })
})

function FilterHarness() {
  const [values, setValues] = useState<Record<string, string>>({})
  return (
    <FilterMenu
      filters={[{ name: 'stock_status', label: 'Stock status', options: [{ value: 'LOW_STOCK', label: 'Low Stock' }] }]}
      values={values}
      onChange={(name, value) => setValues((v) => ({ ...v, [name]: value }))}
      onClear={() => setValues({})}
    />
  )
}

describe('FilterMenu', () => {
  it('opens, applies a filter, shows the active count and clears', async () => {
    const user = userEvent.setup()
    render(<FilterHarness />)
    const toggle = screen.getByRole('button', { name: /filter/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.selectOptions(screen.getByLabelText('Stock status'), 'LOW_STOCK')
    expect(screen.getByLabelText('1 active')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.queryByLabelText('1 active')).not.toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    render(<FilterHarness />)
    await user.click(screen.getByRole('button', { name: /filter/i }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('group', { name: 'Filters' })).not.toBeInTheDocument()
  })
})

describe('StatusChips', () => {
  it('marks the selected chip and reports changes', async () => {
    const onChange = vi.fn()
    const { container } = render(
      <StatusChips
        value="ALL"
        onChange={onChange}
        items={[
          { value: 'ALL', label: 'All', count: 28 },
          { value: 'RECEIVED', label: 'Received', count: 5 },
        ]}
      />,
    )
    expect(screen.getByRole('button', { name: 'All 28' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Received 5' }))
    expect(onChange).toHaveBeenCalledWith('RECEIVED')
    await expectNoAxeViolations(container)
  })
})
