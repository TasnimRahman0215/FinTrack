// Route guards used in App.jsx. They wait for AuthContext to know whether someone is signed in.

import { Navigate, Outlet, useLocation } from 'react-router'

import { Button } from '../../components/ui/Button'
import { ErrorMessage, PageLoader } from '../../components/ui/Feedback'
import { useAuth } from '../../context/AuthContext'

/** Renders child routes for signed-in users; otherwise redirects to /login. */
export function ProtectedRoute() {
  const { me, isLoading, error } = useAuth()
  const location = useLocation()

  if (isLoading) return <PageLoader />
  if (error) {
    return (
      <div className="mx-auto max-w-sm space-y-3 px-4 py-16">
        <ErrorMessage error={error} />
        <Button variant="secondary" onClick={() => window.location.reload()}>
          Try again
        </Button>
      </div>
    )
  }
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}

/** For /login and /signup: once signed in, go to the page the user originally wanted. */
export function GuestRoute() {
  const { me, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <PageLoader />
  if (me) return <Navigate to={location.state?.from ?? '/'} replace />
  return <Outlet />
}
