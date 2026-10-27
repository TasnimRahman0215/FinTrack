import { useEffect } from 'react'

import { useAuth } from '../../context/AuthContext'
import { useScope } from '../../context/ScopeContext'
import { useHousehold } from '../../features/settings/useHousehold'

/**
 * Me | <each other member> | Household tabs, shown in every page header. Changing the tab
 * updates ScopeContext, which refetches the page's data for that view.
 */
export function ScopeSwitcher({ className = '' }) {
  const { scope, setScope } = useScope()
  const { user } = useAuth()
  const { data: household } = useHousehold()

  const others = (household?.members ?? []).filter((m) => m.user_id !== user?.id)
  const options = [
    { value: 'me', label: 'Me' },
    ...others.map((m) => ({ value: `member:${m.user_id}`, label: m.display_name })),
    { value: 'household', label: 'Household' },
  ]

  // A remembered scope can go stale (e.g. a member left); fall back to "me".
  const isStale = Boolean(household) && !options.some((o) => o.value === scope)
  useEffect(() => {
    if (isStale) setScope('me')
  }, [isStale, setScope])

  return (
    <div
      role="tablist"
      aria-label="Whose finances to show"
      className={`flex max-w-full overflow-x-auto rounded-lg bg-slate-100 p-1 dark:bg-slate-800 ${className}`}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="tab"
          aria-selected={scope === opt.value}
          onClick={() => setScope(opt.value)}
          className={`truncate rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors ${
            scope === opt.value
              ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
