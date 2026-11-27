import { render, screen } from '@testing-library/react'
import { expectNoAxeViolations } from '../../test/axe'
import { Banner } from './Banner'
import { Card } from './Card'
import { KpiCard } from './KpiCard'
import { StatusBadge } from './StatusBadge'

describe('KpiCard', () => {
  it('shows label, value and caption, and the highlight variant', async () => {
    const { container } = render(<KpiCard label="Low Stock" value="2" caption="At or below threshold" highlight />)
    const card = screen.getByRole('region', { name: 'Low Stock' })
    expect(card).toHaveClass('ar-kpi--highlight')
    expect(card).toHaveTextContent('2')
    expect(card).toHaveTextContent('At or below threshold')
    await expectNoAxeViolations(container)
  })

  it('shows a loading placeholder', () => {
    render(<KpiCard label="Total Products" value="42" caption="Active in catalog" isPending />)
    expect(screen.queryByText('42')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })
})

describe('StatusBadge', () => {
  it('uses the shared label and tone', () => {
    render(<StatusBadge domain="stock" value="LOW_STOCK" />)
    expect(screen.getByText('Low Stock')).toHaveClass('ar-badge', 'ar-badge--yellow')
  })
})

describe('Card and Banner', () => {
  it('render a titled card and a note', async () => {
    const { container } = render(
      <Card title="New product" aside={<span>Active</span>}>
        <Banner>The product appears in POS once saved.</Banner>
      </Card>,
    )
    expect(screen.getByRole('heading', { name: 'New product' })).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('The product appears in POS once saved.')
    await expectNoAxeViolations(container)
  })
})
