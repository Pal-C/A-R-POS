import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

export function Card({ title, aside, children, className }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx('ar-card', className)}>
      {(title || aside) && (
        <header className="ar-card__header">
          {title && <h2 className="ar-card__title">{title}</h2>}
          {aside && <div className="ar-card__aside">{aside}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
