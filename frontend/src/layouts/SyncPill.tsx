import { useConnectionStatus } from '../lib/connection'

/** "Synced" while requests reach the server, "Offline" otherwise (research R5). */
export function SyncPill() {
  const status = useConnectionStatus()
  return (
    <span className={`ar-sync ar-sync--${status}`} role="status">
      <span className="ar-sync__dot" aria-hidden="true" />
      {status === 'online' ? 'Synced' : 'Offline'}
    </span>
  )
}
