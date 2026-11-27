import { screen, within } from '@testing-library/react'
import { ClipboardList } from 'lucide-react'
import { asAnonymous, asUser, staffUser } from '../test/handlers'
import { renderApp } from '../test/renderApp'
import { workAreas, type WorkArea } from './workAreas'

const restrictedArea: WorkArea = {
  path: '/reports',
  navLabel: 'Reports',
  title: 'Reports',
  subtitle: 'Restricted area',
  icon: ClipboardList,
  permission: 'x.y',
  load: () => import('../pages/placeholders/WorkAreaPlaceholder').then((m) => m.WorkAreaPlaceholder),
}
const areasWithRestricted = [...workAreas, restrictedArea]


describe('routing', () => {
  it.each(workAreas.map((area) => [area.path, area] as const))(
    'redirects signed-out visitors from %s to sign-in',
    async (path) => {
      asAnonymous()
      const { currentPath } = renderApp(path)

      expect(await screen.findByLabelText('Password')).toBeInTheDocument()
      expect(currentPath()).toBe(`/login?next=${encodeURIComponent(path)}`)
    },
  )

  it.each(workAreas.map((area) => [area.path, area] as const))('renders %s for signed-in staff', async (path, area) => {
    asUser()
    renderApp(path)

    expect(await screen.findByRole('heading', { level: 1, name: area.title })).toBeInTheDocument()
    expect(screen.getByText(area.subtitle)).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: area.navLabel })).toHaveAttribute('aria-current', 'page')
  })

  it('navigates between areas from the nav and supports back', async () => {
    asUser()
    const { user, currentPath, router } = renderApp('/')
    const nav = await screen.findByRole('navigation', { name: 'Main' })

    await user.click(within(nav).getByRole('link', { name: 'Services' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Stringing Orders' })).toBeInTheDocument()
    expect(currentPath()).toBe('/stringing')

    await router.navigate(-1)
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeInTheDocument()
  })

  it('redirects the old /products address to Inventory', async () => {
    asUser()
    const { currentPath } = renderApp('/products')

    expect(await screen.findByRole('heading', { level: 1, name: 'Products' })).toBeInTheDocument()
    expect(currentPath()).toBe('/inventory')
  })

  it.each([
    ['signed in', asUser],
    ['signed out', asAnonymous],
  ])('shows Page not found for unknown addresses when %s', async (_label, setup) => {
    setup()
    renderApp('/does-not-exist')

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to Home' })).toHaveAttribute('href', '/')
  })

  it('hides and blocks areas that need a permission the user lacks', async () => {
    asUser()
    renderApp('/reports', { areas: areasWithRestricted })

    expect(await screen.findByRole('heading', { name: "You don't have access to this area" })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).queryByRole('link', { name: 'Reports' })).not.toBeInTheDocument()
  })

  it('shows permission-gated areas to users who have the permission', async () => {
    asUser({ ...staffUser, permissions: ['x.y'] })
    renderApp('/reports', { areas: areasWithRestricted })

    expect(await screen.findByText('This screen is coming soon.')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Reports' })).toBeInTheDocument()
  })

  it('lets superusers into every area', async () => {
    asUser({ ...staffUser, is_superuser: true })
    renderApp('/reports', { areas: areasWithRestricted })

    expect(await screen.findByText('This screen is coming soon.')).toBeInTheDocument()
  })
})
