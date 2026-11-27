import { NavLink } from 'react-router'
import type { WorkArea } from '../routes/workAreas'

/** Navy sidebar; collapses to icons below 992 px (labels stay as accessible names). */
export function Sidebar({ areas }: { areas: WorkArea[] }) {
  return (
    <nav className="ar-shell__nav" aria-label="Main">
      <ul className="ar-nav">
        {areas.map((area) => {
          const Icon = area.icon
          return (
            <li key={area.path}>
              <NavLink to={area.path} end={area.path === '/'} className="ar-nav__link" title={area.navLabel}>
                <Icon size={22} aria-hidden="true" className="ar-nav__icon" />
                <span className="ar-nav__label">{area.navLabel}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
