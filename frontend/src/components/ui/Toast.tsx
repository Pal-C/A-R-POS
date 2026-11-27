import { CircleAlert, CircleCheck, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastApi, type ToastTone } from './ToastContext'

interface ToastItem {
  id: number
  tone: ToastTone
  message: string
}

export const TOAST_DURATION_MS = 5000

function ToastView({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    if (paused) return
    const timer = setTimeout(() => onDismiss(item.id), TOAST_DURATION_MS)
    return () => clearTimeout(timer)
  }, [paused, item.id, onDismiss])

  const Icon = item.tone === 'success' ? CircleCheck : CircleAlert
  return (
    <div
      className={`ar-toast ar-toast--${item.tone}`}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <Icon size={20} aria-hidden="true" />
      <p className="mb-0">{item.message}</p>
      <button type="button" className="ar-toast__close" aria-label="Dismiss notification" onClick={() => onDismiss(item.id)}>
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  )
}

/** Confirmation messages that survive navigation (research R9). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setItems((current) => current.filter((t) => t.id !== id)), [])
  const push = useCallback((tone: ToastTone, message: string) => {
    const id = nextId.current++
    setItems((current) => [...current, { id, tone, message }])
  }, [])
  const api = useMemo<ToastApi>(
    () => ({ success: (m) => push('success', m), error: (m) => push('error', m) }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="ar-toasts" aria-live="polite" aria-atomic="false">
        {items.map((item) => (
          <ToastView key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
