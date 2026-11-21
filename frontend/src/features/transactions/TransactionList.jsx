import { Badge } from '../../components/ui/Badge'
import { Money } from '../../components/ui/Money'
import { formatDay } from '../../lib/dates'

// Renders a list of transactions. Used by the Transactions page and the dashboard.

/** Consecutive transactions with the same date -> [{ date, items }]. Input is newest first. */
function groupByDate(transactions) {
  const groups = []
  for (const t of transactions) {
    const last = groups[groups.length - 1]
    if (last?.date === t.date) last.items.push(t)
    else groups.push({ date: t.date, items: [t] })
  }
  return groups
}

/** Transactions grouped under date headings. Manual ones are clickable when `onEdit` is given. */
export function TransactionList({ transactions, onEdit }) {
  return (
    <div>
      {groupByDate(transactions).map(({ date, items }) => (
        <section key={date}>
          <h3 className="sticky top-0 z-10 bg-slate-50/95 px-4 py-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase backdrop-blur sm:px-5 dark:bg-slate-950/95 dark:text-slate-400">
            {formatDay(date)}
          </h3>
          <ul className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
            {items.map((t) => (
              <TransactionRow key={t.id} txn={t} onEdit={t.editable && onEdit ? () => onEdit(t) : null} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

/** One row: payee (or description), account and notes, amount. A button when editable. */
function TransactionRow({ txn, onEdit }) {
  const title = txn.payee || txn.description
  const content = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{title}</span>
          {txn.pending && <Badge tone="amber">Pending</Badge>}
        </div>
        <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
          {txn.account_name}
          {txn.payee && txn.description && txn.description !== txn.payee && ` · ${txn.description}`}
          {txn.notes && ` · ${txn.notes}`}
        </p>
      </div>
      <Money cents={txn.amount_cents} signed className="text-sm font-medium" />
    </>
  )

  return (
    <li>
      {onEdit ? (
        <button
          type="button"
          onClick={onEdit}
          className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 sm:px-5 dark:hover:bg-slate-800/50"
        >
          {content}
        </button>
      ) : (
        <div className="flex items-center gap-3 px-4 py-3 sm:px-5">{content}</div>
      )}
    </li>
  )
}
