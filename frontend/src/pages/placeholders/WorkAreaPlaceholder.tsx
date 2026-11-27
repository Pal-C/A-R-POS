import { useQuery } from '@tanstack/react-query'
import { QueryState } from '../../components/QueryState'
import type { WorkAreaCount, WorkAreaPageProps } from '../../routes/workAreas'

function RecordCount({ count }: { count: WorkAreaCount }) {
  const query = useQuery({ queryKey: count.queryKey, queryFn: count.fetch })
  return (
    <QueryState
      isPending={query.isPending}
      error={query.error}
      isEmpty={query.data?.count === 0}
      emptyText={`No ${count.noun} yet.`}
    >
      <p>
        {query.data?.count} {count.noun}
      </p>
    </QueryState>
  )
}

/** Stand-in for a work area until its feature delivers the real screen (FR-008). */
export function WorkAreaPlaceholder({ area }: WorkAreaPageProps) {
  return (
    <section className="ar-card ar-page" aria-label={area.title}>
      <p className="text-body-secondary">This screen is coming soon.</p>
      {area.count && <RecordCount count={area.count} />}
    </section>
  )
}
