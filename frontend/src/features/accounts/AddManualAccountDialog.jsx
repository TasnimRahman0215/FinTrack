import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Dialog } from '../../components/ui/Dialog'
import { ErrorMessage } from '../../components/ui/Feedback'
import { Field, Input } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { parseAmountToCents } from '../../lib/money'
import { KindField, OwnerField, VisibilityField } from './AccountFields'
import { isJoint, valueToOwner } from './owner'
import { useCreateAccount } from './useAccounts'

/** "Add a manual account" dialog on the Accounts page. Defaults the owner to the current user. */
export function AddManualAccountDialog({ open, onClose }) {
  return (
    <Dialog open={open} onClose={onClose} title="Add a manual account">
      <AddManualAccountForm onDone={onClose} />
    </Dialog>
  )
}

function AddManualAccountForm({ onDone }) {
  const { user } = useAuth()
  const create = useCreateAccount()
  const [form, setForm] = useState({
    name: '',
    kind: 'checking',
    owner: String(user.id),
    visibility: 'shared',
    opening: '',
  })
  const [error, setError] = useState(null)
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))

  const onSubmit = (e) => {
    e.preventDefault()
    const opening = form.opening.trim() === '' ? 0 : parseAmountToCents(form.opening, { allowNegative: true })
    if (opening === null) return setError('Enter the starting balance as a number, e.g. 250.00')
    setError(null)
    create.mutate(
      {
        name: form.name,
        kind: form.kind,
        owner_user_id: valueToOwner(form.owner),
        visibility: form.visibility,
        opening_balance_cents: opening,
      },
      { onSuccess: onDone },
    )
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        For money SimpleFIN can't see, like cash or a Venmo balance. You add its transactions by hand.
      </p>
      <Field label="Name">
        {(id) => (
          <Input id={id} required maxLength={200} placeholder="Cash" value={form.name} onChange={(e) => set('name')(e.target.value)} />
        )}
      </Field>
      <KindField value={form.kind} onChange={set('kind')} />
      <OwnerField value={form.owner} onChange={set('owner')} />
      <VisibilityField value={form.visibility} onChange={set('visibility')} disabled={isJoint(form.owner)} />
      <Field label="Starting balance" hint="Use a minus sign for money owed, e.g. -120.00">
        {(id) => (
          <Input id={id} inputMode="decimal" placeholder="0.00" value={form.opening} onChange={(e) => set('opening')(e.target.value)} />
        )}
      </Field>
      <ErrorMessage error={error || create.error} />
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={create.isPending}>
          Add account
        </Button>
      </div>
    </form>
  )
}
