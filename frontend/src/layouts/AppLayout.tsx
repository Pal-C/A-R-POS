import { useRef } from 'react'
import { Link, Outlet, useMatches } from 'react-router'
import { useAuth } from '../auth/useAuth'
import type { PageHandle } from '../routes/router'
import type { WorkArea } from '../routes/workAreas'
import { PageHeader } from './PageHeader'
import { Sidebar } from './Sidebar'

function isPageHandle(handle: unknown): handle is PageHandle {
  return typeof handle === 'object' && handle !== null && 'title' in handle
}

export function AppLayout({ areas }: { areas: WorkArea[] }) {
  const { hasPermission } = useAuth()
  const matches = useMatches()
  const mainRef = useRef<HTMLElement>(null)
  const visibleAreas = areas.filter((area) => !area.permission || hasPermission(area.permission))
  const page = [...matches].reverse().map((m) => m.handle).find(isPageHandle)

  return (
    <div className="ar-shell">
      <a
        href="#main"
        className="visually-hidden-focusable ar-skip"
        onClick={(event) => {
          event.preventDefault()
          mainRef.current?.focus()
        }}
      >
        Skip to content
      </a>
      <div className="ar-shell__brand">
        <Link to="/" className="ar-brand">
          <span className="ar-brand__logo" aria-hidden="true" />
          <span className="ar-brand__name">Ace&amp;Rally</span>
        </Link>
      </div>
      <PageHeader title={page?.title ?? ''} subtitle={page?.subtitle} />
      <Sidebar areas={visibleAreas} />
      <main id="main" ref={mainRef} tabIndex={-1} className="ar-shell__main">
        <Outlet />
      </main>
    </div>
  )
}
