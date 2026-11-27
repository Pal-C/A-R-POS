import { safeNextPath } from './safeNextPath'

describe('safeNextPath', () => {
  it('keeps in-app paths with query and hash', () => {
    expect(safeNextPath('/preorders?status=PENDING#top')).toBe('/preorders?status=PENDING#top')
    expect(safeNextPath('/')).toBe('/')
  })

  it.each([
    null,
    undefined,
    '',
    'preorders',
    '//evil.com',
    '//evil.com/path',
    '/\\evil.com',
    'https://evil.com',
    'javascript:alert(1)',
    '/login',
    '/login?next=/x',
    '/login/',
  ])('rejects %s', (raw) => {
    expect(safeNextPath(raw)).toBe('/')
  })
})
