import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { authApi } from '../../api/auth'
import { Button } from '../../components/ui/Button'
import { ErrorMessage, PageLoader } from '../../components/ui/Feedback'
import { Field, Input } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { queryKeys } from '../../lib/queryKeys'
import { AuthLayout } from './AuthLayout'

const MIN_PASSWORD = 8 // must match the backend's SignupIn schema

// /signup. Creates the user and their own household (the backend makes them its owner).
// Invites (phase 1.5) will read `?invite=<token>` here and show "Join <household> as <role>".
export function SignupPage() {
  const { signup } = useAuth()
  const [form, setForm] = useState({ display_name: '', email: '', password: '' })
  const { data: config, isLoading } = useQuery({ queryKey: queryKeys.authConfig, queryFn: authApi.config })

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const onSubmit = (e) => {
    e.preventDefault()
    signup.mutate(form) // GuestRoute redirects once signed in
  }

  const loginLink = (
    <>
      Already have an account?{' '}
      <Link to="/login" className="font-medium text-emerald-600 hover:underline">
        Sign in
      </Link>
    </>
  )

  if (isLoading) return <PageLoader />
  if (config && !config.signup_enabled) {
    return (
      <AuthLayout title="Sign-ups are closed" subtitle="Ask the person who runs this FinTrack server for an invite link." footer={loginLink} />
    )
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="You'll get your own household. You can invite family members later."
      footer={loginLink}
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Your name">
          {(id) => (
            <Input id={id} autoComplete="name" required maxLength={80} value={form.display_name} onChange={set('display_name')} />
          )}
        </Field>
        <Field label="Email">
          {(id) => <Input id={id} type="email" autoComplete="email" required value={form.email} onChange={set('email')} />}
        </Field>
        <Field label="Password" hint={`At least ${MIN_PASSWORD} characters.`}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD}
              maxLength={128}
              value={form.password}
              onChange={set('password')}
            />
          )}
        </Field>
        <ErrorMessage error={signup.error} />
        <Button type="submit" className="w-full" loading={signup.isPending}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
