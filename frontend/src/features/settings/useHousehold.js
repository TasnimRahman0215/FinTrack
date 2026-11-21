// Household data hooks. Members are also used by the scope switcher and owner pickers.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { householdApi } from '../../api/household'
import { queryKeys } from '../../lib/queryKeys'

export function useHousehold() {
  return useQuery({ queryKey: queryKeys.household, queryFn: householdApi.get, staleTime: 60_000 })
}

export function useRenameHousehold() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name) => householdApi.update({ name }),
    onSuccess: (household) => {
      queryClient.setQueryData(queryKeys.household, household)
      queryClient.invalidateQueries({ queryKey: queryKeys.me }) // the sidebar shows the name from /me
    },
  })
}
