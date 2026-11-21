// Main navigation, rendered by both SideNav (desktop) and BottomNav (phones).
// `end: true` makes "/" active only on the dashboard itself, not on every page.
import { ArrowLeftRight, Landmark, LayoutDashboard, Settings } from 'lucide-react'

export const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { to: '/accounts', label: 'Accounts', icon: Landmark },
  { to: '/settings', label: 'Settings', icon: Settings },
]
