import { useRef, useState, type FormEvent } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { MESSAGES, isApiError, toApiError, type FieldErrors } from '../api/errors'
import { safeNextPath } from '../auth/safeNextPath'
import { useAuth } from '../auth/useAuth'
import { ServerUnreachablePage } from './ServerUnreachablePage'
import { SessionCheckingPage } from './SessionCheckingPage'

const END_REASON_MESSAGES = {
  signed_out: 'You have been signed out.',
  expired: MESSAGES.unauthenticated,
} as const

export function LoginPage() {
  const { status, endReason, login } = useAuth()
  const [searchParams] = useSearchParams()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const inFlight = useRef(false)

  if (status === 'checking') return <SessionCheckingPage />
  if (status === 'unreachable') return <ServerUnreachablePage />
  // Signed in (already, or just now): go to the requested in-app page, else Home.
  if (status === 'authenticated') return <Navigate to={safeNextPath(searchParams.get('next'))} replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inFlight.current) return

    const missing: FieldErrors = {}
    if (!username.trim()) missing.username = ['Enter your username.']
    if (!password) missing.password = ['Enter your password.']
    setFormError(null)
    setFieldErrors(missing)
    if (Object.keys(missing).length > 0) return

    inFlight.current = true
    setPending(true)
    try {
      await login(username.trim(), password)
    } catch (error: unknown) {
      const apiError = isApiError(error) ? error : toApiError(error)
      setPassword('')
      setFieldErrors(apiError.fieldErrors)
      setFormError(apiError.kind === 'validation' && apiError.nonFieldErrors.length === 0 ? null : apiError.message)
    } finally {
      inFlight.current = false
      setPending(false)
    }
  }

  const notice = endReason ? END_REASON_MESSAGES[endReason] : null

  return (
    <main className="container py-5" style={{ maxWidth: 420 }}>
      <h1 className="h3 mb-4">Ace&amp;Rally POS — Sign in</h1>
      {notice && !formError && (
        <div className="alert alert-info" role="status">
          {notice}
        </div>
      )}
      {formError && (
        <div className="alert alert-danger" role="alert">
          {formError}
        </div>
      )}
      <form onSubmit={handleSubmit} noValidate>
        <div className="mb-3">
          <label htmlFor="username" className="form-label">
            Username
          </label>
          <input
            id="username"
            name="username"
            className={`form-control${fieldErrors.username ? ' is-invalid' : ''}`}
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={!!fieldErrors.username}
            aria-describedby={fieldErrors.username ? 'username-error' : undefined}
          />
          {fieldErrors.username && (
            <div id="username-error" className="invalid-feedback">
              {fieldErrors.username.join(' ')}
            </div>
          )}
        </div>
        <div className="mb-3">
          <label htmlFor="password" className="form-label">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            className={`form-control${fieldErrors.password ? ' is-invalid' : ''}`}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!fieldErrors.password}
            aria-describedby={fieldErrors.password ? 'password-error' : undefined}
          />
          {fieldErrors.password && (
            <div id="password-error" className="invalid-feedback">
              {fieldErrors.password.join(' ')}
            </div>
          )}
        </div>
        <button type="submit" className="btn btn-primary w-100" disabled={pending}>
          {pending && <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />}
          {pending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
