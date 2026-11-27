import { MESSAGES } from '../api/errors'
import { useAuth } from '../auth/useAuth'

export function ServerUnreachablePage() {
  const { retry, checkError } = useAuth()
  return (
    <main className="container py-5">
      <div className="alert alert-danger" role="alert">
        {checkError ?? MESSAGES.network}
      </div>
      <button type="button" className="btn btn-primary" onClick={retry}>
        Retry
      </button>
    </main>
  )
}
