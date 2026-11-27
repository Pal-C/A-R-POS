import { useAuth } from '../auth/useAuth'

export function HomePage() {
  const { user } = useAuth()
  return <p className="fs-4">Welcome, {user?.display_name}</p>
}
