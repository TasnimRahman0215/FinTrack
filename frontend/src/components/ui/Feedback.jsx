import { CircleAlert, LoaderCircle } from 'lucide-react'

// Loading, error and empty-state components shared by all pages.

export function Spinner({ className = 'h-5 w-5' }) {
  return <LoaderCircle className={`animate-spin ${className}`} aria-hidden="true" />
}

export function PageLoader() {
  return (
    <div className="flex justify-center py-16 text-slate-400" role="status" aria-label="Loading">
      <Spinner className="h-6 w-6" />
    </div>
  )
}

/** Shows an ApiError (or a string). Renders nothing when there's no error. */
export function ErrorMessage({ error, className = '' }) {
  if (!error) return null
  const message = typeof error === 'string' ? error : error.message
  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300 ${className}`}
    >
      <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  )
}

/** Placeholder for an empty list: icon, title, explanation and an optional call to action. */
export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      {Icon && (
        <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          <Icon className="h-6 w-6" aria-hidden="true" />
        </div>
      )}
      <h3 className="text-sm font-semibold">{title}</h3>
      {children && (
        <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">{children}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
