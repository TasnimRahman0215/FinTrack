// Dashboard cards that split the net worth by person and by account type.

import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Money } from '../../components/ui/Money'
import { KIND_LABEL } from '../../lib/labels'

/** Rows of label + amount with a proportional bar (bars use absolute values). */
function BarList({ rows }) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.cents)))
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate">
              {r.label}
              {r.note && <span className="ml-1 text-xs text-slate-400">{r.note}</span>}
            </span>
            <Money cents={r.cents} className="font-medium" />
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div
              className={`h-full rounded-full ${r.cents < 0 ? 'bg-red-400' : 'bg-emerald-500'}`}
              style={{ width: `${(Math.abs(r.cents) / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function MemberBreakdown({ summary }) {
  if (summary.by_owner.length < 2) return null // only interesting with more than one owner
  return (
    <Card>
      <CardHeader title="By person" subtitle="Who holds what in this view" />
      <CardBody>
        <BarList
          rows={summary.by_owner.map((o) => ({ key: o.owner_user_id ?? 'joint', label: o.name, cents: o.total_cents }))}
        />
      </CardBody>
    </Card>
  )
}

export function KindBreakdown({ summary }) {
  if (!summary.by_kind.length) return null
  return (
    <Card>
      <CardHeader title="By account type" />
      <CardBody>
        <BarList
          rows={summary.by_kind.map((k) => ({
            key: k.kind,
            label: KIND_LABEL[k.kind],
            note: `${k.account_count}`,
            cents: k.total_cents,
          }))}
        />
      </CardBody>
    </Card>
  )
}
