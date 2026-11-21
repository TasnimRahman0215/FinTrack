import { Wallet } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { Header } from '../../components/layout/Header'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorMessage, PageLoader } from '../../components/ui/Feedback'
import { useAuth } from '../../context/AuthContext'
import { useScope } from '../../context/ScopeContext'
import { scopeLabel } from '../../lib/labels'
import { useHousehold } from '../settings/useHousehold'
import { TransactionList } from '../transactions/TransactionList'
import { useRecentTransactions } from '../transactions/useTransactions'
import { KindBreakdown, MemberBreakdown } from './Breakdowns'
import { NetWorthCard } from './NetWorthCard'
import { useSummary } from './useSummary'

/**
 * / (home). Net worth and breakdowns on the left, recent transactions on the right, for the
 * current scope. Shows a getting-started prompt when the scope has no accounts.
 */
export function DashboardPage() {
  const { user, canEdit } = useAuth()
  const { scope } = useScope()
  const navigate = useNavigate()
  const { data: household } = useHousehold()
  const summary = useSummary()
  const recent = useRecentTransactions(8)

  const label = scopeLabel(scope, household?.members, user.id)

  return (
    <>
      <Header title={`Hi, ${user.display_name.split(' ')[0]}`} />
      <ErrorMessage error={summary.error} className="mb-4" />

      {summary.isLoading ? (
        <PageLoader />
      ) : summary.data?.account_count === 0 ? (
        <Card>
          <EmptyState
            icon={Wallet}
            title={`Nothing to show for ${label} yet`}
            action={
              canEdit && (
                <div className="flex flex-wrap justify-center gap-2">
                  <Button onClick={() => navigate('/settings')}>Connect with SimpleFIN</Button>
                  <Button variant="secondary" onClick={() => navigate('/accounts')}>
                    Add a manual account
                  </Button>
                </div>
              )
            }
          >
            Connect your bank, credit card and investment accounts through SimpleFIN, or start with a
            manual account. Balances and transactions will show up here.
          </EmptyState>
        </Card>
      ) : (
        summary.data && (
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="space-y-4 lg:col-span-2">
              <NetWorthCard summary={summary.data} label={label} />
              <MemberBreakdown summary={summary.data} />
              <KindBreakdown summary={summary.data} />
            </div>
            <Card className="overflow-clip lg:col-span-3">
              <CardHeader
                title="Recent transactions"
                action={
                  <Link to="/transactions" className="text-sm font-medium text-emerald-600 hover:underline">
                    See all
                  </Link>
                }
              />
              <div className="mt-3">
                {recent.isLoading ? (
                  <PageLoader />
                ) : recent.data?.length ? (
                  <TransactionList transactions={recent.data} />
                ) : (
                  <p className="px-5 pb-5 text-sm text-slate-500 dark:text-slate-400">No transactions yet.</p>
                )}
              </div>
            </Card>
          </div>
        )
      )}
    </>
  )
}
