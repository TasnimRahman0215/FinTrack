// /api/v1/connections (SimpleFIN links). Used by features/settings/useConnections.js.
import { http } from './client'

export const connectionsApi = {
  list: () => http.get('/v1/connections'),
  create: (setupToken) => http.post('/v1/connections', { setup_token: setupToken }),
  remove: (id) => http.delete(`/v1/connections/${id}`),
}
