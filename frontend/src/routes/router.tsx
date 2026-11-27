import { createBrowserRouter, Navigate, type RouteObject } from 'react-router'
import { RequireAuth } from '../auth/RequireAuth'
import { RequirePermission } from '../auth/RequirePermission'
import { AppLayout } from '../layouts/AppLayout'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RouteLoadingPage } from '../pages/RouteLoadingPage'
import { workAreas, type WorkArea, type WorkAreaChild } from './workAreas'

/** Page header metadata read by AppLayout via `useMatches()` (research R4). */
export interface PageHandle {
  title: string
  subtitle: string
}

function lazyPage(area: WorkArea, page: WorkArea | WorkAreaChild): RouteObject['lazy'] {
  return async () => {
    const Page = await page.load()
    return {
      Component: () => (
        <RequirePermission permission={page.permission ?? area.permission}>
          <Page area={area} />
        </RequirePermission>
      ),
    }
  }
}

function areaRoute(area: WorkArea): RouteObject {
  const handle: PageHandle = { title: area.title, subtitle: area.subtitle }
  if (area.path === '/') return { index: true, handle, lazy: lazyPage(area, area) }
  return {
    path: area.path.slice(1),
    children: [
      { index: true, handle, lazy: lazyPage(area, area) },
      ...(area.children ?? []).map(
        (child): RouteObject => ({
          path: child.path,
          handle: { title: child.title, subtitle: child.subtitle } satisfies PageHandle,
          lazy: lazyPage(area, child),
        }),
      ),
    ],
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
              children: [
                ...areas.map(areaRoute),
                // The Products screen lives under Inventory (spec assumptions).
                { path: 'products/*', element: <Navigate to="/inventory" replace /> },
              ],
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
