import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expectNoAxeViolations } from '../../test/axe'
import { ConfirmCheck } from './ConfirmCheck'
import { CheckboxField, MoneyField, NumberField, RadioGroupField, SelectField, TextAreaField, TextField } from './fields'

function Controlled({ initial = '' }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return <MoneyField label="Selling Price" name="selling_price" value={value} onChange={setValue} />
}

describe('fields', () => {
  it('links the label and reports changes', async () => {
    const onChange = vi.fn()
    render(<TextField label="Product Name" name="name" value="" onChange={onChange} required />)
    const input = screen.getByLabelText(/Product Name/)
    expect(input).toHaveAttribute('aria-required', 'true')
    await userEvent.type(input, 'B')
    expect(onChange).toHaveBeenCalledWith('B')
  })

  it('renders errors and links them with aria-describedby', () => {
    render(<TextField label="SKU" name="sku" value="X" onChange={() => {}} error={['A product with this SKU already exists.']} />)
    const input = screen.getByLabelText('SKU')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveClass('is-invalid')
    const errorId = input.getAttribute('aria-describedby')!
    expect(document.getElementById(errorId)).toHaveTextContent('A product with this SKU already exists.')
  })

  it('shows a peso prefix and keeps money as a string', async () => {
    render(<Controlled />)
    const input = screen.getByLabelText('Selling Price')
    expect(screen.getByText('₱')).toBeInTheDocument()
    await userEvent.type(input, '450.50')
    expect(input).toHaveValue('450.50')
    expect(input).toHaveAttribute('inputmode', 'decimal')
  })

  it('supports read-only and numeric inputs', () => {
    render(<NumberField label="Stock Quantity" name="stock" value="89" onChange={() => {}} readOnly />)
    const input = screen.getByLabelText('Stock Quantity')
    expect(input).toHaveAttribute('readonly')
    expect(input).toHaveAttribute('inputmode', 'numeric')
  })

  it('renders select options with a placeholder', async () => {
    const onChange = vi.fn()
    render(
      <SelectField
        label="Category"
        name="category"
        value=""
        onChange={onChange}
        placeholder="Select category"
        options={[{ value: 'RACKET', label: 'Racket' }]}
      />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'RACKET')
    expect(onChange).toHaveBeenCalledWith('RACKET')
  })

  it('renders checkboxes and the confirmation step', async () => {
    const onChange = vi.fn()
    render(
      <>
        <CheckboxField label="Product is active and sellable" name="active" checked onChange={() => {}} />
        <ConfirmCheck label="Are you sure? This hides the product from POS" checked={false} onChange={onChange} />
      </>,
    )
    expect(screen.getByLabelText('Product is active and sellable')).toBeChecked()
    await userEvent.click(screen.getByLabelText('Are you sure? This hides the product from POS'))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <form>
        <TextField label="Name" name="name" value="" onChange={() => {}} error={['Required.']} />
        <MoneyField label="Cost" name="cost" value="" onChange={() => {}} />
        <SelectField label="Category" name="cat" value="" onChange={() => {}} options={[]} placeholder="Select" />
        <TextAreaField label="Reason" name="reason" value="" onChange={() => {}} />
        <CheckboxField label="Active" name="active" checked={false} onChange={() => {}} />
      </form>,
    )
    await expectNoAxeViolations(container)
  })
})

describe('RadioGroupField', () => {
  function Harness() {
    const [value, setValue] = useState('no')
    return (
      <RadioGroupField
        label="Materials"
        name="materials"
        value={value}
        onChange={setValue}
        options={[
          { value: 'no', label: 'Unused' },
          { value: 'yes', label: 'Used' },
        ]}
      />
    )
  }

  it('groups the options under a legend and reports the choice', async () => {
    const { container } = render(<Harness />)
    expect(screen.getByRole('group', { name: 'Materials' })).toBeInTheDocument()
    expect(screen.getByLabelText('Unused')).toBeChecked()
    await userEvent.click(screen.getByLabelText('Used'))
    expect(screen.getByLabelText('Used')).toBeChecked()
    expect(screen.getByLabelText('Unused')).not.toBeChecked()
    await expectNoAxeViolations(container)
  })
})
