import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from '../auth/useAuth'
import { initials } from '../lib/format'

/** Initials avatar, name and role; opens a menu with Sign out. */
export function UserBadge() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocumentClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocumentClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocumentClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null
  const role = user.is_superuser ? 'Admin' : 'Staff'

  return (
    <div className="ar-user" ref={rootRef}>
      <button
        type="button"
        className="ar-user__toggle"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="ar-user__avatar" aria-hidden="true">
          {initials(user.display_name)}
        </span>
        <span className="ar-user__text">
          <span className="ar-user__name" data-testid="current-user">
            {user.display_name}
          </span>
          <span className="ar-user__role">{role}</span>
        </span>
      </button>
      {open && (
        <div id={menuId} className="ar-user__menu">
          <button
            type="button"
            className="btn ar-btn ar-btn--secondary ar-btn--sm w-100"
            disabled={signingOut}
            onClick={async () => {
              setSigningOut(true)
              await logout()
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
