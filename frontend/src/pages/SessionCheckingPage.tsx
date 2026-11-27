export function SessionCheckingPage() {
  return (
    <main className="container py-5 text-center">
      <div role="status" aria-live="polite">
        <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
        Checking your session…
      </div>
    </main>
  )
}
