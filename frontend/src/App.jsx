import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from './components/layout/AppShell'
import { AccountsPage } from './features/accounts/AccountsPage'
import { LoginPage } from './features/auth/LoginPage'
import { GuestRoute, ProtectedRoute } from './features/auth/ProtectedRoute'
import { SignupPage } from './features/auth/SignupPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { SettingsPage } from './features/settings/SettingsPage'
import { TransactionsPage } from './features/transactions/TransactionsPage'

// The route table. GuestRoute pages are for signed-out users; ProtectedRoute pages need a
// session and render inside AppShell (navigation + header).
// Adding a feature = a folder in src/features + a route here (+ a nav item in components/layout/nav.js).
export default function App() {
  return (
    <Routes>
      <Route element={<GuestRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
