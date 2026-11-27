import { Link } from 'react-router'

export function AccessDeniedPage() {
  return (
    <section>
      <h1 className="h3">You don't have access to this area</h1>
      <p>Ask a manager if you need access.</p>
      <Link to="/">Go to Home</Link>
    </section>
  )
}
