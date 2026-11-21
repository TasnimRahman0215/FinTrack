import { ScopeSwitcher } from './ScopeSwitcher'
import { Logo } from './SideNav'

/**
 * Page header used at the top of every page: title + scope switcher (+ optional actions).
 * The logo shows on phones only (desktop has it in the sidebar). Pages that don't depend on
 * scope, like Settings, pass showScope={false}.
 */
export function Header({ title, actions, showScope = true }) {
  return (
    <header className="mb-5 space-y-3">
      <div className="md:hidden">
        <Logo />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        <div className="flex items-center gap-2">
          {showScope && <ScopeSwitcher className="hidden sm:flex" />}
          {actions}
        </div>
      </div>
      {showScope && <ScopeSwitcher className="sm:hidden" />}
    </header>
  )
}
