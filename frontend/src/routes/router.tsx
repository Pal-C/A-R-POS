import { createBrowserRouter, type RouteObject } from 'react-router'
import { RequireAuth } from '../auth/RequireAuth'
import { RequirePermission } from '../auth/RequirePermission'
import { AppLayout } from '../layouts/AppLayout'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RouteLoadingPage } from '../pages/RouteLoadingPage'
import { workAreas, type WorkArea } from './workAreas'

function areaRoute(area: WorkArea): RouteObject {
  const location = area.path === '/' ? { index: true as const } : { path: area.path.slice(1) }
  return {
    ...location,
    lazy: async () => {
      const Page = await area.load()
      return {
        Component: () => (
          <RequirePermission permission={area.permission}>
            <Page area={area} />
          </RequirePermission>
        ),
      }
    },
  }
}

/** Route tree: public sign-in, guarded app shell with one route per work area, 404. */
export function appRoutes(areas: WorkArea[] = workAreas): RouteObject[] {
  return [
    {
      HydrateFallback: RouteLoadingPage,
      children: [
        { path: 'login', Component: LoginPage },
        {
          Component: RequireAuth,
          children: [
            {
              element: <AppLayout areas={areas} />,
              children: areas.map(areaRoute),
            },
          ],
        },
        { path: '*', Component: NotFoundPage },
      ],
    },
  ]
}

export function createAppRouter(areas: WorkArea[] = workAreas) {
  return createBrowserRouter(appRoutes(areas))
}
