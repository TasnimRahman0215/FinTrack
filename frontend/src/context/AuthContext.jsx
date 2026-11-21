// Who is signed in. Provides `useAuth()`: the user, household, role helpers (canEdit, isOwner)
// and the login/signup/logout mutations. Used by route guards, navigation and most pages.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo } from 'react'

import { authApi } from '../api/auth'
import { UNAUTHORIZED_EVENT } from '../api/client'
import { queryKeys } from '../lib/queryKeys'

const AuthContext = createContext(null)

/** GET /auth/me, where "not signed in" (401) is a normal answer rather than an error. */
async function fetchMe() {
  try {
    return await authApi.me()
  } catch (err) {
    if (err.status === 401) return null // not signed in
    throw err
  }
}

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const meQuery = useQuery({ queryKey: queryKeys.me, queryFn: fetchMe, retry: false, staleTime: 5 * 60_000 })

  const signedOut = useCallback(() => {
    queryClient.clear() // drop every cached financial query
    queryClient.setQueryData(queryKeys.me, null)
  }, [queryClient])

  // Any API call that returns 401 (expired session) signs the UI out.
  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, signedOut)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, signedOut)
  }, [signedOut])

  // Start from a clean cache so nothing from a previous user is ever shown.
  const onSignedIn = (me) => {
    queryClient.clear()
    queryClient.setQueryData(queryKeys.me, me)
  }
  const login = useMutation({ mutationFn: authApi.login, onSuccess: onSignedIn })
  const signup = useMutation({ mutationFn: authApi.signup, onSuccess: onSignedIn })
  const logout = useMutation({ mutationFn: authApi.logout, onSettled: signedOut })
  const logoutAll = useMutation({ mutationFn: authApi.logoutAll, onSuccess: signedOut })

  const me = meQuery.data
  const value = useMemo(
    () => ({
      me,
      user: me?.user ?? null,
      household: me?.household ?? null,
      role: me?.role ?? null,
      canEdit: me?.role === 'owner' || me?.role === 'contributor',
      isOwner: me?.role === 'owner',
      isLoading: meQuery.isLoading,
      error: meQuery.error,
      login,
      signup,
      logout,
      logoutAll,
    }),
    [me, meQuery.isLoading, meQuery.error, login, signup, logout, logoutAll],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
