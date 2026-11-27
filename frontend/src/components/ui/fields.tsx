import { useId, type ReactNode } from 'react'
import { cx } from '../../lib/cx'

interface FieldShellProps {
  id: string
  label: string
  error?: string[]
  hint?: string
  required?: boolean
  className?: string
  children: (describedBy: string | undefined) => ReactNode
}

function FieldShell({ id, label, error, hint, required, className, children }: FieldShellProps) {
  const errorId = error?.length ? `${id}-error` : undefined
  const hintId = hint ? `${id}-hint` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined
  return (
    <div className={cx('ar-field', className)}>
      <label htmlFor={id} className="form-label">
        {label}
        {required && (
          <span className="ar-field__required" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      {children(describedBy)}
      {hint && (
        <div id={hintId} className="form-text">
          {hint}
        </div>
      )}
      {errorId && (
        <div id={errorId} className="invalid-feedback d-block">
          {error!.join(' ')}
        </div>
      )}
    </div>
  )
}

interface BaseFieldProps {
  label: string
  name: string
  value: string
  onChange: (value: string) => void
  error?: string[]
  hint?: string
  required?: boolean
  readOnly?: boolean
  disabled?: boolean
  placeholder?: string
  className?: string
}

export interface TextFieldProps extends BaseFieldProps {
  type?: 'text' | 'email' | 'tel' | 'search' | 'date'
  /** For date inputs: latest allowed value (YYYY-MM-DD). */
  max?: string
  autoComplete?: string
  inputMode?: 'text' | 'numeric' | 'decimal' | 'tel'
  maxLength?: number
}

export function TextField({ label, name, value, onChange, error, hint, required, className, type = 'text', ...input }: TextFieldProps) {
  const id = `${name}-${useId()}`
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required} className={className}>
      {(describedBy) => (
        <input
          id={id}
          name={name}
          type={type}
          className={cx('form-control', !!error?.length && 'is-invalid')}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error?.length ? true : undefined}
          aria-describedby={describedBy}
          aria-required={required || undefined}
          {...input}
        />
      )}
    </FieldShell>
  )
}

/** Whole numbers (quantities, thresholds). Kept as a string while typing. */
export function NumberField(props: Omit<TextFieldProps, 'type' | 'inputMode'>) {
  return <TextField {...props} inputMode="numeric" />
}

/** Peso amount, kept as a string (never a float). */
export function MoneyField({ label, name, value, onChange, error, hint, required, className, ...input }: BaseFieldProps) {
  const id = `${name}-${useId()}`
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required} className={className}>
      {(describedBy) => (
        <div className={cx('input-group ar-money', !!error?.length && 'has-validation')}>
          <span className="input-group-text" aria-hidden="true">
            ₱
          </span>
          <input
            id={id}
            name={name}
            className={cx('form-control', !!error?.length && 'is-invalid')}
            inputMode="decimal"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            aria-invalid={error?.length ? true : undefined}
            aria-describedby={describedBy}
            aria-required={required || undefined}
            {...input}
          />
        </div>
      )}
    </FieldShell>
  )
}

export interface SelectOption {
  value: string
  label: string
}

export interface SelectFieldProps extends Omit<BaseFieldProps, 'placeholder'> {
  options: SelectOption[]
  placeholder?: string
}

export function SelectField({ label, name, value, onChange, error, hint, required, className, options, placeholder, readOnly, disabled }: SelectFieldProps) {
  const id = `${name}-${useId()}`
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required} className={className}>
      {(describedBy) => (
        <select
          id={id}
          name={name}
          className={cx('form-select', !!error?.length && 'is-invalid')}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error?.length ? true : undefined}
          aria-describedby={describedBy}
          aria-required={required || undefined}
          disabled={disabled || readOnly}
        >
          {placeholder !== undefined && (
            <option value="" disabled={required}>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  )
}

export function TextAreaField({ label, name, value, onChange, error, hint, required, className, rows = 3, ...input }: BaseFieldProps & { rows?: number }) {
  const id = `${name}-${useId()}`
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required} className={className}>
      {(describedBy) => (
        <textarea
          id={id}
          name={name}
          rows={rows}
          className={cx('form-control', !!error?.length && 'is-invalid')}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error?.length ? true : undefined}
          aria-describedby={describedBy}
          aria-required={required || undefined}
          {...input}
        />
      )}
    </FieldShell>
  )
}

export interface CheckboxFieldProps {
  label: ReactNode
  name: string
  checked: boolean
  onChange: (checked: boolean) => void
  error?: string[]
  disabled?: boolean
  className?: string
}

export function CheckboxField({ label, name, checked, onChange, error, disabled, className }: CheckboxFieldProps) {
  const id = `${name}-${useId()}`
  const errorId = error?.length ? `${id}-error` : undefined
  return (
    <div className={cx('form-check ar-check', className)}>
      <input
        id={id}
        name={name}
        type="checkbox"
        className={cx('form-check-input', !!error?.length && 'is-invalid')}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        aria-describedby={errorId}
      />
      <label htmlFor={id} className="form-check-label">
        {label}
      </label>
      {errorId && (
        <div id={errorId} className="invalid-feedback d-block">
          {error!.join(' ')}
        </div>
      )}
    </div>
  )
}
