import { SyncPill } from './SyncPill'
import { UserBadge } from './UserBadge'

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="ar-shell__header">
      <div className="ar-page-title">
        <h1 className="ar-page-title__heading">{title}</h1>
        {subtitle && <p className="ar-page-title__subtitle">{subtitle}</p>}
      </div>
      <div className="ar-shell__header-aside">
        <SyncPill />
        <UserBadge />
      </div>
    </header>
  )
}
