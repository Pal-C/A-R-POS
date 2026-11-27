import type { LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  icon: LucideIcon
  /** Accessible name; also shown as a tooltip. */
  label: string
  variant?: 'plain' | 'solid'
}

export function IconButton({ icon: Icon, label, variant = 'plain', className, type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      className={cx('ar-icon-btn', `ar-icon-btn--${variant}`, className)}
      aria-label={label}
      title={label}
      {...rest}
    >
      <Icon size={20} aria-hidden="true" />
    </button>
  )
}
