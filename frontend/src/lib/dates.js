// Date formatting helpers shared by the transaction list, forms and sync status.

/** Today as YYYY-MM-DD in the user's local time zone. */
export function todayISO() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** "2026-10-07" -> "Wed, Oct 7" (or "Oct 7, 2025" for other years). Parsed as a calendar date. */
export function formatDay(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  const sameYear = y === new Date().getFullYear()
  return date.toLocaleDateString('en-US', {
    weekday: sameYear ? 'short' : undefined,
    month: 'short',
    day: 'numeric',
    year: sameYear ? undefined : 'numeric',
  })
}

/** Backend datetimes are naive UTC; render them in local time, relative when recent. */
export function formatRelative(utcString) {
  if (!utcString) return 'never'
  const date = new Date(utcString.endsWith('Z') ? utcString : `${utcString}Z`)
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}
