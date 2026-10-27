import { LogOut } from 'lucide-react'
import { NavLink } from 'react-router'

import { useAuth } from '../../context/AuthContext'
import { NAV_ITEMS } from './nav'

/** App logo + name. Also used by Header (phones) and the login/signup layout. */
export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <img src="/favicon.svg" alt="" className="h-7 w-7" />
      <span className="text-base font-semibold tracking-tight">FinTrack</span>
    </div>
  )
}

/** Desktop sidebar (md and up): household name, navigation, and the signed-in user with sign-out. */
export function SideNav() {
  const { user, household, logout } = useAuth()
  return (
    <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-slate-200 bg-white px-3 py-5 md:flex dark:border-slate-800 dark:bg-slate-900">
      <div className="px-2">
        <Logo />
        <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{household?.name}</p>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-1" aria-label="Main">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
              }`
            }
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-2 pt-4 dark:border-slate-800">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{user?.display_name}</p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user?.email}</p>
        </div>
        <button
          type="button"
          onClick={() => logout.mutate()}
          className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  )
}
