import { LogOut } from 'lucide-react'

import { Header } from '../../components/layout/Header'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { useAuth } from '../../context/AuthContext'
import { ROLE_LABEL } from '../../lib/labels'
import { AccountSecuritySection } from './AccountSecuritySection'
import { ConnectionsSection } from './ConnectionsSection'
import { MembersSection } from './MembersSection'
import { SyncStatus } from './SyncStatus'

/** /settings. Connections and sync history on the left; household, profile and sign-in
 * security on the right. */
export function SettingsPage() {
  const { user, role, logout } = useAuth()
  return (
    <>
      <Header title="Settings" showScope={false} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <ConnectionsSection />
          <SyncStatus />
        </div>
        <div className="space-y-4">
          <MembersSection />
          <Card>
            <CardHeader title="Your profile" />
            <CardBody className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{user.display_name}</p>
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                  {user.email} · {ROLE_LABEL[role]}
                </p>
              </div>
              <Button variant="secondary" size="sm" onClick={() => logout.mutate()} loading={logout.isPending}>
                <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out
              </Button>
            </CardBody>
          </Card>
          <AccountSecuritySection />
        </div>
      </div>
    </>
  )
}
