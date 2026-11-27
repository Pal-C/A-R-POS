import { render, screen } from '@testing-library/react'
import { ApiError, MESSAGES, type ApiErrorKind } from '../api/errors'
import { QueryState } from './QueryState'

describe('QueryState', () => {
  it('renders a loading status', () => {
    render(
      <QueryState isPending error={null}>
        content
      </QueryState>,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Loading…')
    expect(screen.queryByText('content')).not.toBeInTheDocument()
  })

  it('renders the empty text when there is nothing to show', () => {
    render(
      <QueryState isPending={false} error={null} isEmpty emptyText="No pre-orders yet.">
        content
      </QueryState>,
    )
    expect(screen.getByText('No pre-orders yet.')).toBeInTheDocument()
  })

  it('renders children on success', () => {
    render(
      <QueryState isPending={false} error={null}>
        content
      </QueryState>,
    )
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it.each<[ApiErrorKind, string]>([
    ['network', MESSAGES.network],
    ['forbidden', MESSAGES.forbidden],
    ['not_found', MESSAGES.not_found],
    ['conflict', 'Stock changed.'],
    ['rate_limited', 'Too many attempts. Try again later.'],
    ['unexpected', MESSAGES.unexpected],
    ['unauthenticated', MESSAGES.unauthenticated],
    ['validation', MESSAGES.validation],
  ])('renders the %s message as an alert', (kind, message) => {
    const error = new ApiError({ kind, status: 400, message, fieldErrors: { quantity: ['Too many.'] } })
    render(
      <QueryState isPending={false} error={error}>
        content
      </QueryState>,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert.textContent).not.toMatch(/[{}[\]]/)
  })

  it('never shows raw details from a non-ApiError', () => {
    render(
      <QueryState isPending={false} error={new Error('{"trace": "secret"}')}>
        content
      </QueryState>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(MESSAGES.unexpected)
    expect(screen.queryByText(/secret/)).not.toBeInTheDocument()
  })
})
