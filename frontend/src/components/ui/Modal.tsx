import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'

export interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  /** While true, Escape and the backdrop don't close the dialog. */
  busy?: boolean
}

/**
 * Native <dialog> modal: the browser provides focus trapping, Escape and the top
 * layer. Focus returns to the element that opened it.
 */
export function Modal({ open, title, onClose, children, footer, busy = false }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const openerRef = useRef<HTMLElement | null>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      openerRef.current = document.activeElement as HTMLElement | null
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '') // environments without <dialog> support (jsdom)
      // Start in the first form field when there is one, else on the first button.
      const first =
        dialog.querySelector<HTMLElement>('.ar-modal__body input, .ar-modal__body textarea, .ar-modal__body select') ??
        dialog.querySelector<HTMLElement>('.ar-modal__body button, .ar-modal__footer button')
      first?.focus()
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
      openerRef.current?.focus()
    }
  }, [open])

  // Restore focus if the dialog unmounts while open.
  useEffect(() => () => openerRef.current?.focus(), [])

  const requestClose = () => {
    if (!busy) onClose()
  }

  return (
    <dialog
      ref={dialogRef}
      className="ar-modal"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault()
        requestClose()
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault()
          requestClose()
        }
      }}
      onMouseDown={(event) => {
        if (event.target === dialogRef.current) requestClose()
      }}
    >
      {open && (
        <div className="ar-modal__content">
          <header className="ar-modal__header">
            <h2 id={titleId} className="ar-modal__title">
              {title}
            </h2>
            <button type="button" className="ar-modal__close" aria-label="Close" onClick={requestClose} disabled={busy}>
              <X size={22} aria-hidden="true" />
            </button>
          </header>
          <div className="ar-modal__body">{children}</div>
          {footer && <footer className="ar-modal__footer">{footer}</footer>}
        </div>
      )}
    </dialog>
  )
}
