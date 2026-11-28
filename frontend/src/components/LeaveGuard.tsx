import { useBlocker } from 'react-router'
import { Button } from './ui/Button'
import { Modal } from './ui/Modal'

/** Asks before leaving a page with unsaved work (no browser confirm dialogs). */
export function LeaveGuard({ when, title, message }: { when: () => boolean; title: string; message: string }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => when() && currentLocation.pathname !== nextLocation.pathname)
  return (
    <Modal
      open={blocker.state === 'blocked'}
      title={title}
      onClose={() => blocker.reset?.()}
      footer={
        <>
          <Button variant="secondary" onClick={() => blocker.reset?.()}>
            Stay
          </Button>
          <Button variant="danger-confirm" onClick={() => blocker.proceed?.()}>
            Leave
          </Button>
        </>
      }
    >
      <p className="mb-0">{message}</p>
    </Modal>
  )
}
