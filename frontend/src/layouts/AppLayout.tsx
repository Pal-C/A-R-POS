import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { useAuth } from '../auth/useAuth'
import type { WorkArea } from '../routes/workAreas'

export function AppLayout({ areas }: { areas: WorkArea[] }) {
  const { user, logout, hasPermission } = useAuth()
  const [signingOut, setSigningOut] = useState(false)
  const visibleAreas = areas.filter((area) => !area.permission || hasPermission(area.permission))

  async function handleSignOut() {
    setSigningOut(true)
    await logout()
  }

  return (
    <div className="d-flex flex-column min-vh-100">
      <header className="navbar navbar-expand border-bottom px-3">
        <span className="navbar-brand">Ace&amp;Rally POS</span>
        <nav aria-label="Main" className="me-auto">
          <ul className="navbar-nav flex-wrap">
            {visibleAreas.map((area) => (
              <li className="nav-item" key={area.path}>
                <NavLink to={area.path} end={area.path === '/'} className="nav-link">
                  {area.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <span className="me-3" data-testid="current-user">
          {user?.display_name}
        </span>
        <button type="button" className="btn btn-outline-secondary btn-sm" onClick={handleSignOut} disabled={signingOut}>
          Sign out
        </button>
      </header>
      <main className="container-fluid py-4 flex-grow-1">
        <Outlet />
      </main>
    </div>
  )
}
