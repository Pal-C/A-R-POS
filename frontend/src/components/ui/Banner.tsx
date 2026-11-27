import { Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

/** Grey information panel used for audit notices and consequences of an action. */
export function Banner({ tone = 'warning', children }: { tone?: 'info' | 'warning'; children: ReactNode }) {
  const Icon = tone === 'warning' ? TriangleAlert : Info
  return (
    <div className={`ar-banner ar-banner--${tone}`} role="note">
      <Icon size={20} aria-hidden="true" className="ar-banner__icon" />
      <div>{children}</div>
    </div>
  )
}
