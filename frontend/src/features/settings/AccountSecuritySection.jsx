import { useMutation, useQueryClient } from '@tanstack/react-query'
import { KeyRound, LogOut } from 'lucide-react'
import { useState } from 'react'

import { authApi } from '../../api/auth'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorMessage } from '../../components/ui/Feedback'
import { Field, Input } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { queryKeys } from '../../lib/queryKeys'
import { RecentActivity } from './RecentActivity'

const EMPTY = { current: '', next: '', confirm: '' }

/**
 * Settings card: change your password (which signs out your other devices) and sign out
 * everywhere (e.g. after losing a phone). Backed by POST /auth/password and /auth/logout-all.
 */
export function AccountSecuritySection() {
  const { logoutAll } = useAuth()
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const queryClient = useQueryClient()
  // Refresh "Recent activity" after either outcome (failed attempts are recorded too).
  const change = useMutation({
    mutationFn: authApi.changePassword,
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.activity }),
  })
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const onSubmit = (e) => {
    e.preventDefault()
    setDone(false)
    if (form.next !== form.confirm) return setError('The new passwords don’t match.')
    setError(null)
    change.mutate(
      { current_password: form.current, new_password: form.next },
      {
        onSuccess: () => {
          setForm(EMPTY)
          setDone(true)
        },
      },
    )
  }

  const onLogoutAll = () => {
    if (window.confirm('Sign out on every device, including this one?')) logoutAll.mutate()
  }

  return (
    <Card>
      <CardHeader title="Sign-in & security" subtitle="Changing your password signs out your other devices." />
      <CardBody className="space-y-4">
        <form onSubmit={onSubmit} className="space-y-3">
          <Field label="Current password">
            {(id) => (
              <Input id={id} type="password" required autoComplete="current-password" value={form.current} onChange={set('current')} />
            )}
          </Field>
          <Field label="New password" hint="At least 8 characters.">
            {(id) => (
              <Input
                id={id}
                type="password"
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                value={form.next}
                onChange={set('next')}
              />
            )}
          </Field>
          <Field label="Confirm new password">
            {(id) => (
              <Input id={id} type="password" required autoComplete="new-password" value={form.confirm} onChange={set('confirm')} />
            )}
          </Field>
          <ErrorMessage error={error || change.error} />
          {done && (
            <p className="text-sm text-emerald-700 dark:text-emerald-400">
              Password changed. Your other devices have been signed out.
            </p>
          )}
          <Button type="submit" size="sm" loading={change.isPending}>
            <KeyRound className="h-4 w-4" aria-hidden="true" /> Change password
          </Button>
        </form>

        <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-4 dark:border-slate-800">
          <p className="text-sm text-slate-600 dark:text-slate-400">Lost a device? End every session at once.</p>
          <Button variant="secondary" size="sm" onClick={onLogoutAll} loading={logoutAll.isPending}>
            <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out everywhere
          </Button>
        </div>
        <ErrorMessage error={logoutAll.error} />

        <div className="border-t border-slate-100 pt-4 dark:border-slate-800">
          <RecentActivity />
        </div>
      </CardBody>
    </Card>
  )
}
