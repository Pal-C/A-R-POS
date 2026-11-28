import { useBlocker } from 'react-router'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'

/** Asks before leaving a page with unsaved work (no browser confirm dialogs). */
export function LeaveGuard({ when, message }: { when: () => boolean; message: string }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => when() && currentLocation.pathname !== nextLocation.pathname)
  return (
    <Modal
      open={blocker.state === 'blocked'}
      title="Leave this sale?"
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
