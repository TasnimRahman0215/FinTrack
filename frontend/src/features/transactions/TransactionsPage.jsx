import { ArrowLeftRight, Plus, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Header } from '../../components/layout/Header'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState, ErrorMessage, PageLoader, Spinner } from '../../components/ui/Feedback'
import { Input, Select } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { useAccounts } from '../accounts/useAccounts'
import { TransactionFormDialog } from './TransactionFormDialog'
import { TransactionList } from './TransactionList'
import { useTransactions } from './useTransactions'

/** `value`, updated only after it stops changing for `delay` ms (so typing doesn't spam the API). */
function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

/**
 * /transactions. All transactions in the current scope, newest first, with search, an account
 * filter and infinite scroll. Contributors can add manual transactions or click one to edit.
 */
export function TransactionsPage() {
  const { canEdit } = useAuth()
  const [search, setSearch] = useState('')
  const [accountId, setAccountId] = useState('')
  const [dialog, setDialog] = useState({ open: false, txn: null })
  const q = useDebounced(search.trim())

  const { data: accounts } = useAccounts()
  // Phase 3 adds start/end (timeframes) to these filters; the API already supports them.
  const filters = { q: q || undefined, account_id: accountId || undefined }
  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } = useTransactions(filters)
  const transactions = data?.pages.flatMap((p) => p.items) ?? []

  // Load the next page when the bottom of the list scrolls into view.
  const sentinel = useRef(null)
  useEffect(() => {
    const el = sentinel.current
    if (!el || !hasNextPage) return
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && !isFetchingNextPage && fetchNextPage(),
      { rootMargin: '400px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const filtered = Boolean(q || accountId)

  return (
    <>
      <Header
        title="Transactions"
        actions={
          canEdit && (
            <Button size="sm" onClick={() => setDialog({ open: true, txn: null })}>
              <Plus className="h-4 w-4" aria-hidden="true" /> Add
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <Input
            type="search"
            placeholder="Search description, payee or notes"
            aria-label="Search transactions"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          aria-label="Filter by account"
          className="sm:w-56"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
        >
          <option value="">All accounts</option>
          {(accounts ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.display_name || a.name}
            </option>
          ))}
        </Select>
      </div>

      <ErrorMessage error={error} className="mb-4" />
      <Card className="overflow-clip">
        {isLoading ? (
          <PageLoader />
        ) : transactions.length === 0 ? (
          <EmptyState icon={ArrowLeftRight} title={filtered ? 'No matching transactions' : 'No transactions yet'}>
            {filtered
              ? 'Try a different search or account.'
              : 'Transactions appear here after your first SimpleFIN sync, or when you add one by hand.'}
          </EmptyState>
        ) : (
          <>
            <TransactionList transactions={transactions} onEdit={canEdit ? (txn) => setDialog({ open: true, txn }) : null} />
            <div ref={sentinel} className="flex justify-center py-4">
              {isFetchingNextPage ? (
                <Spinner className="h-5 w-5 text-slate-400" />
              ) : hasNextPage ? (
                <Button variant="ghost" size="sm" onClick={() => fetchNextPage()}>
                  Load more
                </Button>
              ) : (
                <span className="text-xs text-slate-400">That's everything</span>
              )}
            </div>
          </>
        )}
      </Card>

      <TransactionFormDialog
        open={dialog.open}
        txn={dialog.txn}
        onClose={() => setDialog({ open: false, txn: null })}
      />
    </>
  )
}
