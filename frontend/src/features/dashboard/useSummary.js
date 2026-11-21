import { useQuery } from '@tanstack/react-query'

import { summaryApi } from '../../api/summary'
import { useScope } from '../../context/ScopeContext'
import { queryKeys } from '../../lib/queryKeys'

/** Dashboard totals for the current scope (GET /summary). Refetches when the scope changes. */
export function useSummary() {
  const { scope } = useScope()
  return useQuery({ queryKey: queryKeys.summary(scope), queryFn: () => summaryApi.get({ scope }) })
}
