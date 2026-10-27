// Data hooks for connections and syncing, used by the Settings page.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { connectionsApi } from '../../api/connections'
import { syncApi } from '../../api/sync'
import { queryKeys } from '../../lib/queryKeys'
import { useInvalidateFinancialData } from '../accounts/useAccounts'

/** A brand-new connection syncs in the background; poll until its first sync lands. */
const isSyncing = (connections) =>
  connections?.some((c) => !c.last_synced_at && c.status === 'active') ?? false

/** The household's connections, plus `syncing` while a first sync is in progress. */
export function useConnections() {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateFinancialData()
  const query = useQuery({
    queryKey: queryKeys.connections,
    queryFn: connectionsApi.list,
    refetchInterval: (q) => (isSyncing(q.state.data) ? 3000 : false),
  })

  // When a background sync finishes, refresh everything that shows synced data.
  const wasSyncing = useRef(false)
  const syncing = isSyncing(query.data)
  useEffect(() => {
    if (wasSyncing.current && !syncing) {
      invalidate()
      queryClient.invalidateQueries({ queryKey: queryKeys.syncRuns })
    }
    wasSyncing.current = syncing
  }, [syncing, invalidate, queryClient])

  return { ...query, syncing }
}

export function useSyncRuns() {
  return useQuery({ queryKey: queryKeys.syncRuns, queryFn: syncApi.runs })
}

export function useAddConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: connectionsApi.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.connections }),
  })
}

export function useRemoveConnection() {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateFinancialData()
  return useMutation({
    mutationFn: connectionsApi.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.connections })
      invalidate()
    },
  })
}

export function useSyncNow() {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateFinancialData()
  return useMutation({
    mutationFn: syncApi.syncNow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.connections })
      queryClient.invalidateQueries({ queryKey: queryKeys.syncRuns })
      invalidate()
    },
  })
}
