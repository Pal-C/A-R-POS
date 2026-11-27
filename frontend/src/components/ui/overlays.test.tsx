import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expectNoAxeViolations } from '../../test/axe'
import { Modal } from './Modal'
import { TOAST_DURATION_MS, ToastProvider } from './Toast'
import { useToast } from './useToast'

function ModalHarness({ busy = false }: { busy?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Remove BG66</button>
      <Modal open={open} title="Remove Product" onClose={() => setOpen(false)} busy={busy} footer={<button>Confirm</button>}>
        <p>Body</p>
      </Modal>
    </>
  )
}

describe('Modal', () => {
  it('opens with a labelled dialog, closes on Escape and returns focus', async () => {
    const user = userEvent.setup()
    render(<ModalHarness />)
    const opener = screen.getByRole('button', { name: 'Remove BG66' })
    await user.click(opener)

    const dialog = screen.getByRole('dialog', { name: 'Remove Product' })
    expect(dialog).toHaveTextContent('Body')
    await expectNoAxeViolations(dialog)

    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Remove Product' })).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('closes with the close button', async () => {
    const user = userEvent.setup()
    render(<ModalHarness />)
    await user.click(screen.getByRole('button', { name: 'Remove BG66' }))
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Remove Product' })).not.toBeInTheDocument()
  })

  it('does not close while busy', async () => {
    const user = userEvent.setup()
    render(<ModalHarness busy />)
    await user.click(screen.getByRole('button', { name: 'Remove BG66' }))
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: 'Remove Product' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeDisabled()
  })
})

function ToastHarness() {
  const toast = useToast()
  return <button onClick={() => toast.success('Product saved.')}>Notify</button>
}

describe('Toast', () => {
  afterEach(() => vi.useRealTimers())

  it('announces, then dismisses itself after the timeout', () => {
    vi.useFakeTimers()
    render(
      <ToastProvider>
        <ToastHarness />
      </ToastProvider>,
    )
    act(() => screen.getByRole('button', { name: 'Notify' }).click())
    expect(screen.getByText('Product saved.')).toBeInTheDocument()
    expect(screen.getByText('Product saved.').closest('[aria-live]')).toHaveAttribute('aria-live', 'polite')
    act(() => vi.advanceTimersByTime(TOAST_DURATION_MS))
    expect(screen.queryByText('Product saved.')).not.toBeInTheDocument()
  })

  it('stays while hovered and can be dismissed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render(
      <ToastProvider>
        <ToastHarness />
      </ToastProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Notify' }))
    await user.hover(screen.getByText('Product saved.'))
    act(() => vi.advanceTimersByTime(TOAST_DURATION_MS * 2))
    expect(screen.getByText('Product saved.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Dismiss notification' }))
    expect(screen.queryByText('Product saved.')).not.toBeInTheDocument()
  })
})
