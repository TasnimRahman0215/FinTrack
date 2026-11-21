// TanStack Query cache keys, used by every features/*/use*.js hook.
// Every data key includes the scope, so each view (Me / member / Household) is cached separately.
export const queryKeys = {
  me: ['me'],
  authConfig: ['auth-config'],
  household: ['household'],
  connections: ['connections'],
  syncRuns: ['sync-runs'],
  activity: ['security-activity'],
  accounts: (scope, opts = {}) => ['accounts', scope, opts],
  transactions: (scope, filters = {}) => ['transactions', scope, filters],
  summary: (scope) => ['summary', scope],
}

// Anything derived from account balances or transactions: invalidated after a sync or any edit.
export const FINANCIAL_DATA_KEYS = [['accounts'], ['transactions'], ['summary']]
