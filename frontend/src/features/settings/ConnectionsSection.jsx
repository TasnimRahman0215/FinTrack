import { Link2, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { EmptyState, ErrorMessage, PageLoader, Spinner } from '../../components/ui/Feedback'
import { useAuth } from '../../context/AuthContext'
import { formatRelative } from '../../lib/dates'
import { CONNECTION_STATUS } from '../../lib/labels'
import { AddConnectionForm } from './AddConnectionForm'
import { useConnections, useRemoveConnection, useSyncNow } from './useConnections'

/** Settings card listing SimpleFIN connections, with "Sync now", add and remove. */
export function ConnectionsSection() {
  const { canEdit } = useAuth()
  const [adding, setAdding] = useState(false)
  const { data: connections, isLoading, error, syncing } = useConnections()
  const syncNow = useSyncNow()
  const remove = useRemoveConnection()

  const skipped = syncNow.data?.skipped ?? []
  const onRemove = (c) => {
    if (window.confirm(`Remove "${c.label}"? Its ${c.account_count} account(s) and their transactions will be deleted from FinTrack.`)) {
      remove.mutate(c.id)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Connections"
        subtitle="Banks, cards and brokerages linked through SimpleFIN. Syncs automatically every few hours."
        action={
          canEdit &&
          connections?.length > 0 && (
            <Button size="sm" variant="secondary" onClick={() => syncNow.mutate()} loading={syncNow.isPending}>
              {!syncNow.isPending && <RefreshCw className="h-4 w-4" aria-hidden="true" />} Sync now
            </Button>
          )
        }
      />
      <CardBody className="space-y-3">
        <ErrorMessage error={error || syncNow.error || remove.error} />
        {skipped.map((s) => (
          <p key={s.connection_id} className="text-sm text-amber-700 dark:text-amber-400">
            {s.reason}
          </p>
        ))}

        {isLoading ? (
          <PageLoader />
        ) : connections.length === 0 ? (
          <EmptyState icon={Link2} title="No connections yet">
            Link your accounts once in SimpleFIN Bridge (about $15/year), then paste the setup token here.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200 dark:divide-slate-800 dark:ring-slate-800">
            {connections.map((c) => {
              const status = CONNECTION_STATUS[c.status] ?? { label: c.status, tone: 'slate' }
              // Never synced and no error yet: the first sync is still running in the background.
              const firstSync = !c.last_synced_at && c.status === 'active'
              return (
                <li key={c.id} className="flex items-start gap-3 p-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">{c.label}</span>
                      {firstSync ? (
                        <Badge tone="blue">
                          <Spinner className="h-3 w-3" /> First sync…
                        </Badge>
                      ) : (
                        <Badge tone={status.tone}>{status.label}</Badge>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {c.account_count} account{c.account_count === 1 ? '' : 's'} · synced{' '}
                      {formatRelative(c.last_synced_at)}
                    </p>
                    {c.last_error && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">{c.last_error}</p>
                    )}
                  </div>
                  {canEdit && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onRemove(c)}
                      aria-label={`Remove ${c.label}`}
                      title="Remove connection"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {syncing && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            The first sync pulls up to 90 days of history and can take a minute.
          </p>
        )}

        {canEdit && (
          <Button variant={connections?.length ? 'secondary' : 'primary'} onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" /> Add SimpleFIN connection
          </Button>
        )}
      </CardBody>

      <Dialog open={adding} onClose={() => setAdding(false)} title="Connect with SimpleFIN">
        <AddConnectionForm onDone={() => setAdding(false)} />
      </Dialog>
    </Card>
  )
}
