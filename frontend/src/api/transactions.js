// /api/v1/transactions. Used by features/transactions/useTransactions.js.
import { http } from './client'

export const transactionsApi = {
  // filters: { account_id, start, end, q }. `opts.signal` lets TanStack Query cancel stale requests.
  list: ({ scope, cursor, limit = 50, ...filters }, opts) =>
    http.get('/v1/transactions', { scope, cursor, limit, ...filters }, opts),
  create: (data) => http.post('/v1/transactions', data),
  update: (id, data) => http.patch(`/v1/transactions/${id}`, data),
  remove: (id) => http.delete(`/v1/transactions/${id}`),
}
