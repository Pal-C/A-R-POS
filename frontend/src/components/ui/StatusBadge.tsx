import { badgeFor, type BadgeDomain, type StatusBadgeSpec } from '../../lib/statusBadges'

export type StatusBadgeProps = { domain: BadgeDomain; value: string } | { spec: StatusBadgeSpec }

export function StatusBadge(props: StatusBadgeProps) {
  const spec = 'spec' in props ? props.spec : badgeFor(props.domain, props.value)
  return <span className={`ar-badge ar-badge--${spec.tone}`}>{spec.label}</span>
}
