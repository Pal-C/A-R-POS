import { CheckboxField } from './fields'

/** The explicit "I understand…" step required before destructive actions (Principle III). */
export function ConfirmCheck({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return <CheckboxField name="confirm" label={label} checked={checked} onChange={onChange} className="ar-confirm" />
}
