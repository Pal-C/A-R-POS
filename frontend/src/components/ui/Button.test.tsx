import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Pencil, Plus } from 'lucide-react'
import { expectNoAxeViolations } from '../../test/axe'
import { Button } from './Button'
import { IconButton } from './IconButton'

describe('Button', () => {
  it.each(['primary', 'secondary', 'danger-confirm', 'ghost'] as const)('renders the %s variant', (variant) => {
    render(<Button variant={variant}>Save</Button>)
    expect(screen.getByRole('button', { name: 'Save' })).toHaveClass('ar-btn', `ar-btn--${variant}`)
  })

  it('defaults to type="button" and renders an icon', () => {
    const { container } = render(<Button icon={Plus}>Add product</Button>)
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })

  it('is disabled and marked busy while busy', async () => {
    const onClick = vi.fn()
    render(
      <Button busy onClick={onClick}>
        Save
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <>
        <Button>Save</Button>
        <IconButton icon={Pencil} label="Edit BG66 Ultimax" />
      </>,
    )
    await expectNoAxeViolations(container)
  })
})

describe('IconButton', () => {
  it('uses the label as its accessible name and tooltip', () => {
    render(<IconButton icon={Pencil} label="Edit BG66 Ultimax" />)
    const button = screen.getByRole('button', { name: 'Edit BG66 Ultimax' })
    expect(button).toHaveAttribute('title', 'Edit BG66 Ultimax')
  })
})
