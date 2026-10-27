// Display labels for backend enum values (account kinds, roles, statuses) and scopes.
// Keep the values in sync with backend/app/models/enums.py.

export const ACCOUNT_KINDS = [
  { value: 'checking', label: 'Checking', group: 'Cash' },
  { value: 'savings', label: 'Savings', group: 'Cash' },
  { value: 'credit', label: 'Credit card', group: 'Credit cards' },
  { value: 'investment', label: 'Investment', group: 'Investments' },
  { value: 'loan', label: 'Loan', group: 'Loans' },
  { value: 'other', label: 'Other', group: 'Other' },
]

export const KIND_LABEL = Object.fromEntries(ACCOUNT_KINDS.map((k) => [k.value, k.label]))
export const KIND_GROUP = Object.fromEntries(ACCOUNT_KINDS.map((k) => [k.value, k.group]))
// Order of the account groups on the Accounts page and dashboard.
export const GROUP_ORDER = ['Cash', 'Credit cards', 'Investments', 'Loans', 'Other']

export const ROLE_LABEL = { owner: 'Owner', contributor: 'Contributor', reader: 'Reader' }

// Label and Badge tone for each status.
export const CONNECTION_STATUS = {
  active: { label: 'Connected', tone: 'green' },
  error: { label: 'Error', tone: 'red' },
  reauth_required: { label: 'Needs reconnect', tone: 'amber' },
}

export const SYNC_STATUS = {
  running: { label: 'Running', tone: 'slate' },
  success: { label: 'Success', tone: 'green' },
  partial: { label: 'With warnings', tone: 'amber' },
  failed: { label: 'Failed', tone: 'red' },
}

/** "Me" / "Sam" / "Household" for a scope key, given the household members. */
export function scopeLabel(scope, members = [], meId) {
  if (scope === 'household') return 'Household'
  if (scope === 'me') return 'Me'
  const id = Number(scope.split(':')[1])
  if (id === meId) return 'Me'
  return members.find((m) => m.user_id === id)?.display_name ?? 'Member'
}
