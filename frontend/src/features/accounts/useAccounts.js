// Data hooks for accounts (TanStack Query). Used by the Accounts page, the transaction form and
// anything that needs the account list.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { accountsApi } from '../../api/accounts'
import { useScope } from '../../context/ScopeContext'
import { FINANCIAL_DATA_KEYS, queryKeys } from '../../lib/queryKeys'

/** Accounts in the current scope (or in `scope`, when given). */
export function useAccounts({ includeHidden = false, scope: fixedScope } = {}) {
  const { scope: currentScope } = useScope()
  const scope = fixedScope ?? currentScope
  return useQuery({
    queryKey: queryKeys.accounts(scope, { includeHidden }),
    queryFn: () => accountsApi.list({ scope, includeHidden }),
  })
}

/**
 * Returns a function that marks accounts, transactions and summaries stale in every scope, so
 * they refetch. Call it after anything that changes balances (edits, syncs).
 */
export function useInvalidateFinancialData() {
  const queryClient = useQueryClient()
  return useCallback(
    () => Promise.all(FINANCIAL_DATA_KEYS.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
    [queryClient],
  )
}

function useAccountMutation(mutationFn) {
  const invalidate = useInvalidateFinancialData()
  return useMutation({ mutationFn, onSuccess: invalidate })
}

export const useCreateAccount = () => useAccountMutation(accountsApi.create)
export const useUpdateAccount = () => useAccountMutation(({ id, ...data }) => accountsApi.update(id, data))
export const useDeleteAccount = () => useAccountMutation(accountsApi.remove)
