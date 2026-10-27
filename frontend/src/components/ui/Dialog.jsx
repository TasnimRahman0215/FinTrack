import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

/**
 * Accessible modal built on <dialog>. Children mount only while open, so forms reset each time.
 * On phones it docks to the bottom like a sheet.
 */
export function Dialog({ open, onClose, title, children, footer }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()} // click on backdrop
      className="m-0 mt-auto w-full max-w-none rounded-t-2xl bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-950/50 sm:m-auto sm:max-w-lg sm:rounded-2xl dark:bg-slate-900 dark:text-slate-100"
    >
      {open && (
        <div className="flex max-h-[90dvh] flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <h2 className="text-base font-semibold">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer && (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-5 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] dark:border-slate-800">
              {footer}
            </div>
          )}
        </div>
      )}
    </dialog>
  )
}
