// Every money amount in the UI goes through this, so formatting stays consistent.

import { formatMoney, formatSignedMoney } from '../../lib/money'

/** Amount display. `signed` shows +/− and colours income green (for transactions). */
export function Money({ cents, currency = 'USD', signed = false, className = '' }) {
  const tone = signed && cents > 0 ? 'text-emerald-600 dark:text-emerald-400' : ''
  return (
    <span className={`tabular whitespace-nowrap ${tone} ${className}`}>
      {signed ? formatSignedMoney(cents, currency) : formatMoney(cents, currency)}
    </span>
  )
}
