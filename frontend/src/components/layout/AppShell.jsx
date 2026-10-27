import { Outlet } from 'react-router'

import { BottomNav } from './BottomNav'
import { SideNav } from './SideNav'

/**
 * Layout for every signed-in page (see App.jsx): sidebar on desktop, tab bar on phones, and the
 * current page rendered in <Outlet />. Padding leaves room for the phone notch and tab bar.
 */
export function AppShell() {
  return (
    <div className="min-h-dvh md:pl-60">
      <SideNav />
      <main className="mx-auto max-w-5xl px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-24 sm:px-6 md:pt-8 md:pb-10 lg:px-8">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  )
}
