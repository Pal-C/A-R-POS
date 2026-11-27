import { useAuth } from '../auth/useAuth'

export function HomePage() {
  const { user } = useAuth()
  return (
    <section>
      <h1 className="h3">Welcome, {user?.display_name}</h1>
    </section>
  )
}
