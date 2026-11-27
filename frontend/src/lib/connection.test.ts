import { getConnectionStatus, setConnectionStatus, subscribeConnectionStatus } from './connection'

afterEach(() => setConnectionStatus('online'))

describe('connection status store', () => {
  it('notifies subscribers on change only', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeConnectionStatus(listener)
    setConnectionStatus('offline')
    setConnectionStatus('offline')
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
    setConnectionStatus('online')
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('follows the browser online/offline events', () => {
    window.dispatchEvent(new Event('offline'))
    expect(getConnectionStatus()).toBe('offline')
    window.dispatchEvent(new Event('online'))
    expect(getConnectionStatus()).toBe('online')
  })
})
