import { Landmark, Plus } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { Header } from '../../components/layout/Header'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState, ErrorMessage, PageLoader } from '../../components/ui/Feedback'
import { useAuth } from '../../context/AuthContext'
import { GROUP_ORDER, KIND_GROUP } from '../../lib/labels'
import { useHousehold } from '../settings/useHousehold'
import { AccountEditDialog } from './AccountEditDialog'
import { AccountGroup } from './AccountGroup'
import { AddManualAccountDialog } from './AddManualAccountDialog'
import { useAccounts } from './useAccounts'

/**
 * /accounts. Every account in the current scope, grouped by type (lib/labels.js GROUP_ORDER),
 * with buttons to add a manual account or edit one (contributors and owners only).
 */
export function AccountsPage() {
  const { user, canEdit } = useAuth()
  const navigate = useNavigate()
  const [showHidden, setShowHidden] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const { data: accounts, isLoading, error } = useAccounts({ includeHidden: showHidden })
  const { data: household } = useHousehold()
  const members = household?.members ?? []

  const groups = GROUP_ORDER.map((group) => ({
    group,
    accounts: (accounts ?? []).filter((a) => KIND_GROUP[a.kind] === group),
  })).filter((g) => g.accounts.length)

  return (
    <>
      <Header
        title="Accounts"
        actions={
          canEdit && (
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" /> Manual account
            </Button>
          )
        }
      />

      <label className="mb-4 flex w-fit items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
        <input
          type="checkbox"
          checked={showHidden}
          onChange={(e) => setShowHidden(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600"
        />
        Show hidden accounts
      </label>

      <ErrorMessage error={error} className="mb-4" />
      {isLoading ? (
        <PageLoader />
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState
            icon={Landmark}
            title="No accounts in this view"
            action={
              canEdit && (
                <div className="flex flex-wrap justify-center gap-2">
                  <Button onClick={() => navigate('/settings')}>Connect with SimpleFIN</Button>
                  <Button variant="secondary" onClick={() => setAdding(true)}>
                    Add manual account
                  </Button>
                </div>
              )
            }
          >
            Connect your banks through SimpleFIN, or add a manual account for cash. Accounts other members
            keep private won't show up here.
          </EmptyState>
        </Card>
      ) : (
        <div className="space-y-4">
          {groups.map(({ group, accounts: list }) => (
            <AccountGroup
              key={group}
              title={group}
              accounts={list}
              members={members}
              meId={user.id}
              canEdit={canEdit}
              onEdit={setEditing}
            />
          ))}
        </div>
      )}

      <AddManualAccountDialog open={adding} onClose={() => setAdding(false)} />
      <AccountEditDialog account={editing} onClose={() => setEditing(null)} />
    </>
  )
}
