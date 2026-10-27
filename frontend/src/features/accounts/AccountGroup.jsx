import { EyeOff, Lock, Pencil, Users } from 'lucide-react'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Money } from '../../components/ui/Money'
import { formatRelative } from '../../lib/dates'

/** "Me", a member's name, or "Joint" for an account. */
export function OwnerBadge({ account, members, meId }) {
  if (account.owner_user_id === null) {
    return (
      <Badge tone="blue">
        <Users className="h-3 w-3" aria-hidden="true" /> Joint
      </Badge>
    )
  }
  const name =
    account.owner_user_id === meId
      ? 'Me'
      : (members.find((m) => m.user_id === account.owner_user_id)?.display_name ?? 'Former member')
  return <Badge>{name}</Badge>
}

/** One group on the Accounts page (e.g. "Credit cards") with its total and account rows. */
export function AccountGroup({ title, accounts, members, meId, canEdit, onEdit }) {
  const total = accounts.reduce((sum, a) => sum + a.balance_cents, 0)
  return (
    <Card>
      <div className="flex items-center justify-between px-4 pt-4 pb-2 sm:px-5">
        <h2 className="text-sm font-semibold">{title}</h2>
        <Money cents={total} className="text-sm font-semibold" />
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {accounts.map((a) => (
          <li key={a.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className={`truncate text-sm font-medium ${a.is_hidden ? 'text-slate-400' : ''}`}>
                  {a.display_name || a.name}
                </span>
                <OwnerBadge account={a} members={members} meId={meId} />
                {a.visibility === 'private' && a.owner_user_id !== null && (
                  <Badge tone="amber">
                    <Lock className="h-3 w-3" aria-hidden="true" /> Private
                  </Badge>
                )}
                {a.is_hidden && (
                  <Badge>
                    <EyeOff className="h-3 w-3" aria-hidden="true" /> Hidden
                  </Badge>
                )}
              </div>
              <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
                {a.source === 'manual' ? 'Manual account' : (a.org_name ?? 'Synced')}
                {a.source !== 'manual' && a.balance_as_of && ` · updated ${formatRelative(a.balance_as_of)}`}
              </p>
            </div>
            <Money cents={a.balance_cents} currency={a.currency} className="text-sm font-medium" />
            {canEdit && (
              <button
                type="button"
                onClick={() => onEdit(a)}
                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                aria-label={`Edit ${a.display_name || a.name}`}
              >
                <Pencil className="h-4 w-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
