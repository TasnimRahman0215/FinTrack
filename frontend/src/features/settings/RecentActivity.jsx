import { useQuery } from '@tanstack/react-query'

import { authApi } from '../../api/auth'
import { ErrorMessage, Spinner } from '../../components/ui/Feedback'
import { formatRelative } from '../../lib/dates'
import { SECURITY_EVENT } from '../../lib/labels'
import { queryKeys } from '../../lib/queryKeys'

/** A short browser description from a user-agent string, e.g. "Safari on iPhone". */
function describeBrowser(ua) {
  if (!ua) return 'Unknown browser'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Firefox\//.test(ua)
      ? 'Firefox'
      : /Chrome\//.test(ua)
        ? 'Chrome'
        : /Safari\//.test(ua)
          ? 'Safari'
          : 'Browser'
  const device = /iPhone/.test(ua)
    ? 'iPhone'
    : /iPad/.test(ua)
      ? 'iPad'
      : /Android/.test(ua)
        ? 'Android'
        : /Mac OS X/.test(ua)
          ? 'Mac'
          : /Windows/.test(ua)
            ? 'Windows'
            : /Linux/.test(ua)
              ? 'Linux'
              : 'unknown device'
  return `${browser} on ${device}`
}

/** Your last sign-ins and security changes, so you can spot anything you didn't do. */
export function RecentActivity() {
  const { data, isLoading, error } = useQuery({ queryKey: queryKeys.activity, queryFn: authApi.activity })

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Recent activity</h3>
      <ErrorMessage error={error} />
      {isLoading ? (
        <Spinner className="h-4 w-4 text-slate-400" />
      ) : (
        <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200 dark:divide-slate-800 dark:ring-slate-800">
          {(data ?? []).slice(0, 10).map((e, i) => {
            const meta = SECURITY_EVENT[e.event] ?? { label: e.event }
            return (
              <li key={i} className="flex items-start justify-between gap-3 px-3 py-2 text-sm">
                <div className="min-w-0">
                  <p className={meta.alert ? 'font-medium text-amber-700 dark:text-amber-400' : 'font-medium'}>
                    {meta.label}
                  </p>
                  <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                    {describeBrowser(e.user_agent)}
                    {e.ip && ` · ${e.ip}`}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{formatRelative(e.created_at)}</span>
              </li>
            )
          })}
        </ul>
      )}
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Don’t recognise something? Change your password and sign out everywhere.
      </p>
    </div>
  )
}
