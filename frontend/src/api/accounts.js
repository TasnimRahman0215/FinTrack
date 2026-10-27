// /api/v1/accounts. Used by features/accounts/useAccounts.js.
import { http } from './client'

export const accountsApi = {
  list: ({ scope, includeHidden = false }) =>
    http.get('/v1/accounts', { scope, include_hidden: includeHidden || undefined }),
  create: (data) => http.post('/v1/accounts', data),
  update: (id, data) => http.patch(`/v1/accounts/${id}`, data),
  remove: (id) => http.delete(`/v1/accounts/${id}`),
}
