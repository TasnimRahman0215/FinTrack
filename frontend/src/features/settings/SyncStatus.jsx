import { Badge } from '../../components/ui/Badge'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { formatRelative } from '../../lib/dates'
import { SYNC_STATUS } from '../../lib/labels'
import { useSyncRuns } from './useConnections'

/** Settings card with the last 10 sync runs and any warnings. Hidden until something has synced. */
export function SyncStatus() {
  const { data: runs } = useSyncRuns()
  if (!runs?.length) return null

  return (
    <Card>
      <CardHeader title="Sync history" subtitle="The most recent sync attempts and anything SimpleFIN reported." />
      <CardBody>
        <ul className="space-y-3">
          {runs.slice(0, 10).map((r) => {
            const status = SYNC_STATUS[r.status] ?? { label: r.status, tone: 'slate' }
            return (
              <li key={r.id} className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={status.tone}>{status.label}</Badge>
                  <span className="text-slate-600 dark:text-slate-300">{formatRelative(r.started_at)}</span>
                  <span className="text-xs text-slate-400">({r.trigger})</span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {r.accounts_seen} accounts · {r.txns_new} new · {r.txns_updated} updated
                  {r.txns_removed > 0 && ` · ${r.txns_removed} pending removed`}
                </p>
                {r.errors.map((err) => (
                  <p key={err} className="mt-0.5 text-xs text-amber-700 dark:text-amber-400">
                    {err}
                  </p>
                ))}
              </li>
            )
          })}
        </ul>
      </CardBody>
    </Card>
  )
}
