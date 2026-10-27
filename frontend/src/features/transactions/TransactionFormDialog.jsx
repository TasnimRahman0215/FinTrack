import { useQueries } from '@tanstack/react-query'
import { useState } from 'react'

import { accountsApi } from '../../api/accounts'
import { Button } from '../../components/ui/Button'
import { Dialog } from '../../components/ui/Dialog'
import { ErrorMessage } from '../../components/ui/Feedback'
import { Field, Input, Segmented, Select, Textarea } from '../../components/ui/Form'
import { todayISO } from '../../lib/dates'
import { centsToInput, parseAmountToCents } from '../../lib/money'
import { queryKeys } from '../../lib/queryKeys'
import { useCreateTransaction, useDeleteTransaction, useUpdateTransaction } from './useTransactions'

// The add/edit dialog for manual transactions, opened from the Transactions page.

/**
 * Manual accounts the user can add to: their own (incl. private) plus shared/joint ones.
 * Fetched for "me" and "household" regardless of the current scope, then merged.
 */
function useManualAccounts() {
  const results = useQueries({
    queries: ['me', 'household'].map((scope) => ({
      queryKey: queryKeys.accounts(scope, { includeHidden: false }),
      queryFn: () => accountsApi.list({ scope }),
    })),
  })
  const byId = new Map()
  for (const r of results) for (const a of r.data ?? []) if (a.source === 'manual') byId.set(a.id, a)
  return { accounts: [...byId.values()], isLoading: results.some((r) => r.isLoading) }
}

/** Add (txn = null) or edit a manual transaction. */
export function TransactionFormDialog({ open, txn, onClose }) {
  return (
    <Dialog open={open} onClose={onClose} title={txn ? 'Edit transaction' : 'Add transaction'}>
      <TransactionForm txn={txn} onDone={onClose} />
    </Dialog>
  )
}

function TransactionForm({ txn, onDone }) {
  const { accounts, isLoading } = useManualAccounts()
  const create = useCreateTransaction()
  const update = useUpdateTransaction()
  const remove = useDeleteTransaction()
  const [form, setForm] = useState(() => ({
    account_id: txn ? String(txn.account_id) : '',
    date: txn?.date ?? todayISO(),
    direction: txn && txn.amount_cents > 0 ? 'income' : 'expense',
    amount: txn ? centsToInput(Math.abs(txn.amount_cents)) : '',
    description: txn?.description ?? '',
    notes: txn?.notes ?? '',
  }))
  const [error, setError] = useState(null)
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))
  // Default to the first account once the list has loaded.
  const accountId = form.account_id || (accounts[0] ? String(accounts[0].id) : '')

  const onSubmit = (e) => {
    e.preventDefault()
    const cents = parseAmountToCents(form.amount)
    if (!cents) return setError('Enter an amount greater than zero, e.g. 12.50')
    if (!accountId) return setError('Pick an account.')
    setError(null)
    const body = {
      account_id: Number(accountId),
      date: form.date,
      amount_cents: form.direction === 'expense' ? -cents : cents, // the API uses negative = money out
      description: form.description,
      notes: form.notes || null,
    }
    if (txn) update.mutate({ id: txn.id, ...body }, { onSuccess: onDone })
    else create.mutate(body, { onSuccess: onDone })
  }

  const onDelete = () => {
    if (window.confirm('Delete this transaction?')) remove.mutate(txn.id, { onSuccess: onDone })
  }

  if (!isLoading && accounts.length === 0) {
    return (
      <p className="text-sm text-slate-600 dark:text-slate-400">
        Manual transactions go into manual accounts (like Cash), so they never double-count what your bank
        syncs. Add a manual account on the <strong>Accounts</strong> page first.
      </p>
    )
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Segmented
        label="Transaction type"
        value={form.direction}
        onChange={set('direction')}
        options={[
          { value: 'expense', label: 'Expense' },
          { value: 'income', label: 'Income' },
        ]}
      />
      <div className="grid grid-cols-2 gap-3">
        <Field label="Amount">
          {(id) => (
            <Input
              id={id}
              inputMode="decimal"
              required
              placeholder="0.00"
              value={form.amount}
              onChange={(e) => set('amount')(e.target.value)}
              autoFocus
            />
          )}
        </Field>
        <Field label="Date">
          {(id) => <Input id={id} type="date" required value={form.date} onChange={(e) => set('date')(e.target.value)} />}
        </Field>
      </div>
      <Field label="Description">
        {(id) => (
          <Input
            id={id}
            required
            maxLength={500}
            placeholder="Farmers market"
            value={form.description}
            onChange={(e) => set('description')(e.target.value)}
          />
        )}
      </Field>
      <Field label="Account">
        {(id) => (
          <Select id={id} value={accountId} onChange={(e) => set('account_id')(e.target.value)}>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.display_name || a.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Notes (optional)">
        {(id) => <Textarea id={id} rows={2} maxLength={2000} value={form.notes} onChange={(e) => set('notes')(e.target.value)} />}
      </Field>
      <ErrorMessage error={error || create.error || update.error || remove.error} />
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
        {txn ? (
          <Button variant="ghost" className="text-red-600 dark:text-red-400" onClick={onDelete} loading={remove.isPending}>
            Delete
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button variant="secondary" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={create.isPending || update.isPending}>
            {txn ? 'Save' : 'Add'}
          </Button>
        </div>
      </div>
    </form>
  )
}
