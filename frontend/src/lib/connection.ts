import { useSyncExternalStore } from 'react'

/** Whether the last request reached the server (research R5). Drives the header's sync pill. */
export type ConnectionStatus = 'online' | 'offline'

let status: ConnectionStatus = typeof navigator !== 'undefined' && navigator.onLine === false ? 'offline' : 'online'
const listeners = new Set<() => void>()

export function getConnectionStatus(): ConnectionStatus {
  return status
}

export function setConnectionStatus(next: ConnectionStatus): void {
  if (next === status) return
  status = next
  listeners.forEach((listener) => listener())
}

export function subscribeConnectionStatus(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => setConnectionStatus('online'))
  window.addEventListener('offline', () => setConnectionStatus('offline'))
}

export function useConnectionStatus(): ConnectionStatus {
  return useSyncExternalStore(subscribeConnectionStatus, getConnectionStatus, getConnectionStatus)
}
