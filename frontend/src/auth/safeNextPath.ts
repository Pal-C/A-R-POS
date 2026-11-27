/**
 * Returns `raw` only if it is an in-app path; otherwise "/" (FR-008, no open redirect).
 * Rejects protocol-relative (`//`, `/\`) and absolute URLs, and the sign-in page itself.
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) return '/'
  // Resolve against a dummy origin to catch anything the browser would treat as external.
  const base = 'http://app.invalid'
  let url: URL
  try {
    url = new URL(raw, base)
  } catch {
    return '/'
  }
  if (url.origin !== base) return '/'
  if (url.pathname === '/login' || url.pathname.startsWith('/login/')) return '/'
  return `${url.pathname}${url.search}${url.hash}`
}
