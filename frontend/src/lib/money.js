// Money helpers. The API always uses integer cents; these convert to and from what people
// see and type, without floating-point rounding errors.

// Intl.NumberFormat is slow to construct, so keep one per currency.
const formatters = new Map()

/** A currency formatter, falling back to USD for unknown currency codes. */
function formatter(currency) {
  if (!formatters.has(currency)) {
    let f
    try {
      f = new Intl.NumberFormat('en-US', { style: 'currency', currency })
    } catch {
      f = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
    }
    formatters.set(currency, f)
  }
  return formatters.get(currency)
}

/** 123456 -> "$1,234.56"; -4567 -> "-$45.67" */
export function formatMoney(cents, currency = 'USD') {
  return formatter(currency).format((cents ?? 0) / 100)
}

/** Like formatMoney but always shows a sign: "+$3,200.00" / "−$45.67". */
export function formatSignedMoney(cents, currency = 'USD') {
  const abs = formatter(currency).format(Math.abs(cents ?? 0) / 100)
  if (!cents) return abs
  return cents > 0 ? `+${abs}` : `−${abs}`
}

/**
 * Parse a user-typed amount into integer cents without floating-point errors.
 * Accepts "12", "12.3", "1,234.56", "$45", and (when allowNegative) "-45.10".
 * Returns null when the input isn't a valid amount.
 */
export function parseAmountToCents(input, { allowNegative = false } = {}) {
  const cleaned = String(input ?? '').replace(/[\s$,]/g, '')
  const match = cleaned.match(/^(-)?(\d*)(?:\.(\d{0,2}))?$/)
  if (!match || (!match[2] && !match[3])) return null
  if (match[1] && !allowNegative) return null
  const whole = Number(match[2] || 0)
  const frac = Number((match[3] || '').padEnd(2, '0'))
  const cents = whole * 100 + frac
  return match[1] ? -cents : cents
}

/** 4567 -> "45.67" (for pre-filling inputs). */
export function centsToInput(cents) {
  if (cents === null || cents === undefined) return ''
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}
