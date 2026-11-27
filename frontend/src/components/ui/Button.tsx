import type { LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'

export type ButtonVariant = 'primary' | 'secondary' | 'danger-confirm' | 'ghost'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  icon?: LucideIcon
  /** Disables the button and shows a spinner while an action runs. */
  busy?: boolean
  size?: 'md' | 'sm'
}

export function Button({
  variant = 'primary',
  icon: Icon,
  busy = false,
  size = 'md',
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx('btn ar-btn', `ar-btn--${variant}`, size === 'sm' && 'ar-btn--sm', className)}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy ? (
        <span className="spinner-border spinner-border-sm" aria-hidden="true" />
      ) : (
        Icon && <Icon size={18} aria-hidden="true" />
      )}
      <span>{children}</span>
    </button>
  )
}
