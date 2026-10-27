import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Dialog } from '../../components/ui/Dialog'
import { ErrorMessage } from '../../components/ui/Feedback'
import { Field, Input } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { centsToInput, parseAmountToCents } from '../../lib/money'
import { KindField, OwnerField, VisibilityField } from './AccountFields'
import { isJoint, ownerToValue, valueToOwner } from './owner'
import { useDeleteAccount, useUpdateAccount } from './useAccounts'

/**
 * Edit an account from the Accounts page. Synced accounts: display name, type, owner, visibility
 * and hidden. Manual accounts can also change their name and starting balance, or be deleted.
 * Open when `account` is set.
 */
export function AccountEditDialog({ account, onClose }) {
  return (
    <Dialog open={Boolean(account)} onClose={onClose} title="Edit account">
      {account && <AccountEditForm account={account} onDone={onClose} />}
    </Dialog>
  )
}

function AccountEditForm({ account, onDone }) {
  const { user, isOwner } = useAuth()
  const update = useUpdateAccount()
  const remove = useDeleteAccount()
  const isManual = account.source === 'manual'
  // Mirrors the API rule: only the account's owner (or the household owner) can re-assign it.
  const canReassign = account.owner_user_id === null || account.owner_user_id === user.id || isOwner

  const [form, setForm] = useState({
    name: account.name,
    display_name: account.display_name ?? '',
    kind: account.kind,
    owner: ownerToValue(account.owner_user_id),
    visibility: account.visibility,
    is_hidden: account.is_hidden,
    opening: centsToInput(account.opening_balance_cents),
  })
  const [error, setError] = useState(null)
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))

  const onSubmit = (e) => {
    e.preventDefault()
    const body = { id: account.id, display_name: form.display_name, kind: form.kind, is_hidden: form.is_hidden }
    // Only send owner/visibility when allowed, so the API doesn't reject the whole update.
    if (canReassign) {
      body.owner_user_id = valueToOwner(form.owner)
      body.visibility = form.visibility
    }
    if (isManual) {
      const opening = form.opening.trim() === '' ? 0 : parseAmountToCents(form.opening, { allowNegative: true })
      if (opening === null) return setError('Enter the starting balance as a number, e.g. 250.00')
      body.name = form.name
      body.opening_balance_cents = opening
    }
    setError(null)
    update.mutate(body, { onSuccess: onDone })
  }

  const onDelete = () => {
    if (window.confirm(`Delete "${account.name}" and all of its transactions? This can't be undone.`)) {
      remove.mutate(account.id, { onSuccess: onDone })
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {isManual ? (
        <Field label="Name">
          {(id) => <Input id={id} required maxLength={200} value={form.name} onChange={(e) => set('name')(e.target.value)} />}
        </Field>
      ) : (
        <Field label="Display name" hint={`From your bank: ${account.name}${account.org_name ? ` · ${account.org_name}` : ''}`}>
          {(id) => (
            <Input id={id} maxLength={200} placeholder={account.name} value={form.display_name} onChange={(e) => set('display_name')(e.target.value)} />
          )}
        </Field>
      )}
      <KindField value={form.kind} onChange={set('kind')} />
      <OwnerField value={form.owner} onChange={set('owner')} disabled={!canReassign} />
      <VisibilityField
        value={form.visibility}
        onChange={set('visibility')}
        disabled={!canReassign || isJoint(form.owner)}
      />
      {isManual && (
        <Field label="Starting balance">
          {(id) => <Input id={id} inputMode="decimal" value={form.opening} onChange={(e) => set('opening')(e.target.value)} />}
        </Field>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.is_hidden}
          onChange={(e) => set('is_hidden')(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600"
        />
        Hide this account (leaves it out of totals and lists)
      </label>
      <ErrorMessage error={error || update.error || remove.error} />
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
        {isManual ? (
          <Button variant="ghost" className="text-red-600 dark:text-red-400" onClick={onDelete} loading={remove.isPending}>
            Delete account
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button variant="secondary" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={update.isPending}>
            Save
          </Button>
        </div>
      </div>
    </form>
  )
}
