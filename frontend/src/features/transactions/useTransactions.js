// Data hooks for transactions (TanStack Query). Mutations refresh balances and totals too.

import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query'

import { transactionsApi } from '../../api/transactions'
import { useScope } from '../../context/ScopeContext'
import { queryKeys } from '../../lib/queryKeys'
import { useInvalidateFinancialData } from '../accounts/useAccounts'

/** Infinite, cursor-paginated list. filters: { account_id, start, end, q } */
export function useTransactions(filters = {}, { pageSize = 50 } = {}) {
  const { scope } = useScope()
  return useInfiniteQuery({
    queryKey: queryKeys.transactions(scope, { ...filters, pageSize }),
    queryFn: ({ pageParam, signal }) =>
      transactionsApi.list({ scope, cursor: pageParam, limit: pageSize, ...filters }, { signal }),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}

/** Just the newest few (dashboard). */
export function useRecentTransactions(limit = 8) {
  const { scope } = useScope()
  return useQuery({
    queryKey: queryKeys.transactions(scope, { recent: limit }),
    queryFn: () => transactionsApi.list({ scope, limit }),
    select: (page) => page.items,
  })
}

function useTxnMutation(mutationFn) {
  const invalidate = useInvalidateFinancialData()
  return useMutation({ mutationFn, onSuccess: invalidate })
}

export const useCreateTransaction = () => useTxnMutation(transactionsApi.create)
export const useUpdateTransaction = () => useTxnMutation(({ id, ...data }) => transactionsApi.update(id, data))
export const useDeleteTransaction = () => useTxnMutation(transactionsApi.remove)
