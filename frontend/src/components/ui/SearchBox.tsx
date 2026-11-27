import { Search, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'

export interface SearchBoxProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  /** Accessible name; defaults to the placeholder. */
  label?: string
  debounceMs?: number
}

/** Search input that reports changes after a short pause in typing. */
export function SearchBox({ value, onChange, placeholder = 'Search', label, debounceMs = 250 }: SearchBoxProps) {
  const [text, setText] = useState(value)
  const [committed, setCommitted] = useState(value)
  const id = useId()
  const latest = useRef(onChange)
  useEffect(() => {
    latest.current = onChange
  }, [onChange])

  // Follow external resets (e.g. "Clear filters") by adjusting state during render.
  if (value !== committed) {
    setCommitted(value)
    setText(value)
  }

  useEffect(() => {
    if (text === value) return
    const timer = setTimeout(() => latest.current(text), debounceMs)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only typing should schedule a change
  }, [text, debounceMs])

  return (
    <div className="ar-search">
      <label htmlFor={id} className="visually-hidden">
        {label ?? placeholder}
      </label>
      <Search className="ar-search__icon" size={20} aria-hidden="true" />
      <input
        id={id}
        type="search"
        className="form-control"
        placeholder={placeholder}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {text && (
        <button
          type="button"
          className="ar-search__clear"
          aria-label="Clear search"
          onClick={() => {
            setText('')
            onChange('')
          }}
        >
          <X size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}
