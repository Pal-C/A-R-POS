import { http, HttpResponse } from 'msw'
import type { CurrentUser } from '../api/auth'
import { server } from './server'

export const api = (path: string) => `*/api${path}`

export const staffUser: CurrentUser = {
  id: 1,
  username: 'maria',
  first_name: 'Maria',
  last_name: 'Santos',
  display_name: 'Maria Santos',
  is_superuser: false,
  permissions: [],
}

export const unauthenticated = () =>
  HttpResponse.json({ detail: 'Authentication credentials were not provided.' }, { status: 401 })

export const emptyPage = () => HttpResponse.json({ count: 0, next: null, previous: null, results: [] })

export const defaultHandlers = [
  http.get(api('/auth/csrf/'), () => new HttpResponse(null, { status: 204 })),
  http.get(api('/auth/me/'), unauthenticated),
  http.post(api('/auth/logout/'), () => new HttpResponse(null, { status: 204 })),
  http.post(api('/auth/login/'), () =>
    HttpResponse.json({ non_field_errors: ['Invalid username or password.'] }, { status: 400 }),
  ),
  // Work-area placeholders load record counts.
  ...['/sales/', '/products/', '/customers/', '/stringing/orders/', '/preorders/'].map((path) =>
    http.get(api(path), emptyPage),
  ),
]

/** Simulates a server session for `user`: `me` succeeds and login with password "secret" works. */
export function asUser(user: CurrentUser = staffUser): void {
  let signedIn = true
  server.use(
    http.get(api('/auth/me/'), () => (signedIn ? HttpResponse.json(user) : unauthenticated())),
    http.post(api('/auth/logout/'), () => {
      signedIn = false
      return new HttpResponse(null, { status: 204 })
    }),
  )
}

/** No session; signing in as `user` with password "secret" succeeds and starts one. */
export function asAnonymous(user: CurrentUser = staffUser): void {
  let signedIn = false
  server.use(
    http.get(api('/auth/me/'), () => (signedIn ? HttpResponse.json(user) : unauthenticated())),
    http.post(api('/auth/login/'), async ({ request }) => {
      const body = (await request.json()) as { username: string; password: string }
      if (body.username === user.username && body.password === 'secret') {
        signedIn = true
        return HttpResponse.json(user)
      }
      return HttpResponse.json({ non_field_errors: ['Invalid username or password.'] }, { status: 400 })
    }),
  )
}
