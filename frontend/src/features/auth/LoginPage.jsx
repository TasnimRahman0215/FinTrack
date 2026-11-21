import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { authApi } from '../../api/auth'
import { Button } from '../../components/ui/Button'
import { ErrorMessage } from '../../components/ui/Feedback'
import { Field, Input } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { queryKeys } from '../../lib/queryKeys'
import { AuthLayout } from './AuthLayout'

/** /login. The "Create an account" link only shows while the server allows sign-ups. */
export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { data: config } = useQuery({ queryKey: queryKeys.authConfig, queryFn: authApi.config })

  const onSubmit = (e) => {
    e.preventDefault()
    login.mutate({ email, password }) // GuestRoute redirects once signed in
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to see your finances."
      footer={
        config?.signup_enabled && (
          <>
            New here?{' '}
            <Link to="/signup" className="font-medium text-emerald-600 hover:underline">
              Create an account
            </Link>
          </>
        )
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Email">
          {(id) => (
            <Input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Field>
        <Field label="Password">
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <ErrorMessage error={login.error} />
        <Button type="submit" className="w-full" loading={login.isPending}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}
