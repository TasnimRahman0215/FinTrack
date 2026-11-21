// Which view the user is looking at. Provides `useScope()` -> { scope, setScope }. Read by
// every data hook (scope is part of each query key) and changed by layout/ScopeSwitcher.jsx.

import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

const STORAGE_KEY = 'fintrack.scope'
const ScopeContext = createContext(null)

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY) || 'me'
  } catch {
    return 'me'
  }
}

/**
 * The current view: "me", "household" or "member:<id>".
 * A `?scope=` in the URL wins (so links are shareable); otherwise the last choice is remembered.
 */
export function ScopeProvider({ children }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [stored, setStored] = useState(readStored)
  const scope = searchParams.get('scope') || stored

  const setScope = useCallback(
    (next) => {
      setStored(next)
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* private mode: the choice just won't be remembered */
      }
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev)
          params.set('scope', next)
          return params
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const value = useMemo(() => ({ scope, setScope }), [scope, setScope])
  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>
}

export function useScope() {
  const ctx = useContext(ScopeContext)
  if (!ctx) throw new Error('useScope must be used inside <ScopeProvider>')
  return ctx
}
