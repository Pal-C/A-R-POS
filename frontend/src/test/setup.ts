import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { server } from './server'

function clearCookies(): void {
  for (const cookie of document.cookie.split(';')) {
    const name = cookie.split('=')[0]?.trim()
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
  }
}

// The full suite runs many app-level tests in parallel; allow slower machines time
// to settle async UI before failing a findBy/waitFor.
configure({ asyncUtilTimeout: 3000 })

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  clearCookies()
})
afterAll(() => server.close())
