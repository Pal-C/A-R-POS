import { http as mswHttp, HttpResponse } from 'msw'
import { api } from '../test/handlers'
import { server } from '../test/server'
import { apiDelete, apiGet, apiGetPage, apiPatch, apiPost, http, setUnauthenticatedHandler } from './client'
import { ApiError } from './errors'

afterEach(() => setUnauthenticatedHandler(null))

describe('api client', () => {
  it('sends credentials to the configured base URL', async () => {
    expect(http.defaults.withCredentials).toBe(true)
    let seenUrl = ''
    server.use(
      mswHttp.get(api('/ping/'), ({ request }) => {
        seenUrl = new URL(request.url).pathname
        return HttpResponse.json({ ok: true })
      }),
    )
    await expect(apiGet('/ping/')).resolves.toEqual({ ok: true })
    expect(seenUrl).toBe('/api/ping/')
  })

  it.each([
    ['POST', () => apiPost('/thing/', {}), mswHttp.post],
    ['PATCH', () => apiPatch('/thing/', {}), mswHttp.patch],
    ['DELETE', () => apiDelete('/thing/'), mswHttp.delete],
  ] as const)('echoes the csrftoken cookie on %s', async (_method, call, handler) => {
    document.cookie = 'csrftoken=tok-123; path=/'
    let header: string | null = null
    server.use(
      handler(api('/thing/'), ({ request }) => {
        header = request.headers.get('X-CSRFToken')
        return HttpResponse.json({})
      }),
    )
    await call()
    expect(header).toBe('tok-123')
  })

  it('always rejects with ApiError', async () => {
    server.use(mswHttp.get(api('/broken/'), () => HttpResponse.json({ detail: 'nope' }, { status: 404 })))
    const error = await apiGet('/broken/').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).kind).toBe('not_found')
  })

  it('calls the unauthenticated handler once for concurrent 401s', async () => {
    const handler = vi.fn()
    setUnauthenticatedHandler(handler)
    server.use(mswHttp.get(api('/secret/:n/'), () => HttpResponse.json({}, { status: 401 })))

    await Promise.allSettled([apiGet('/secret/1/'), apiGet('/secret/2/'), apiGet('/secret/3/')])

    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('does not re-arm on a data request that succeeds after the 401', async () => {
    const handler = vi.fn()
    setUnauthenticatedHandler(handler)
    server.use(
      mswHttp.get(api('/secret/'), () => HttpResponse.json({}, { status: 401 })),
      mswHttp.get(api('/ok/'), () => HttpResponse.json({})),
    )
    await apiGet('/secret/').catch(() => {})
    await apiGet('/ok/')
    await apiGet('/secret/').catch(() => {})
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('re-arms the unauthenticated handler after a successful sign-in', async () => {
    const handler = vi.fn()
    setUnauthenticatedHandler(handler)
    server.use(
      mswHttp.get(api('/secret/'), () => HttpResponse.json({}, { status: 401 })),
      mswHttp.post(api('/auth/login/'), () => HttpResponse.json({ id: 1 })),
    )
    await apiGet('/secret/').catch(() => {})
    await apiPost('/auth/login/', { username: 'maria', password: 'secret' })
    await apiGet('/secret/').catch(() => {})
    expect(handler).toHaveBeenCalledTimes(2)
  })

  it.each(['/auth/login/', '/auth/me/'])('does not call the handler for a 401 from %s', async (path) => {
    const handler = vi.fn()
    setUnauthenticatedHandler(handler)
    server.use(
      mswHttp.get(api(path), () => HttpResponse.json({}, { status: 401 })),
      mswHttp.post(api(path), () => HttpResponse.json({}, { status: 401 })),
    )
    await apiGet(path).catch(() => {})
    await apiPost(path).catch(() => {})
    expect(handler).not.toHaveBeenCalled()
  })

  it('does not call the handler for a 403', async () => {
    const handler = vi.fn()
    setUnauthenticatedHandler(handler)
    server.use(mswHttp.post(api('/x/'), () => HttpResponse.json({}, { status: 403 })))
    await apiPost('/x/').catch(() => {})
    expect(handler).not.toHaveBeenCalled()
  })

  it('returns pages and serializes list params, dropping undefined', async () => {
    let query = ''
    server.use(
      mswHttp.get(api('/items/'), ({ request }) => {
        query = new URL(request.url).search
        return HttpResponse.json({ count: 1, next: null, previous: null, results: [{ id: 1 }] })
      }),
    )
    const page = await apiGetPage<{ id: number }>('/items/', {
      page: 2,
      search: 'yonex',
      ordering: '-created_at',
      status: 'PENDING',
      customer: undefined,
    })
    expect(page.results[0]?.id).toBe(1)
    const params = new URLSearchParams(query)
    expect(Object.fromEntries(params)).toEqual({
      page: '2',
      search: 'yonex',
      ordering: '-created_at',
      status: 'PENDING',
    })
  })
})
