import { Card, CardBody } from '../../components/ui/Card'
import { Money } from '../../components/ui/Money'
import { formatRelative } from '../../lib/dates'

/** Headline net worth for the scope, with assets, liabilities and last sync time. */
export function NetWorthCard({ summary, label }) {
  return (
    <Card>
      <CardBody>
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Net worth · {label}</p>
        <Money cents={summary.net_worth_cents} className="mt-1 block text-3xl font-semibold tracking-tight sm:text-4xl" />
        <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 dark:border-slate-800">
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Assets</dt>
            <dd>
              <Money cents={summary.assets_cents} className="text-base font-semibold text-emerald-600 dark:text-emerald-400" />
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Liabilities</dt>
            <dd>
              <Money cents={summary.liabilities_cents} className="text-base font-semibold text-red-600 dark:text-red-400" />
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-slate-400">
          {summary.account_count} account{summary.account_count === 1 ? '' : 's'} · last synced{' '}
          {formatRelative(summary.last_synced_at)}
        </p>
      </CardBody>
    </Card>
  )
}
