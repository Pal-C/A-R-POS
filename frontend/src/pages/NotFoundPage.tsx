import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <main className="container py-5">
      <h1 className="h3">Page not found</h1>
      <p>The page you asked for doesn't exist.</p>
      <Link to="/">Go to Home</Link>
    </main>
  )
}
