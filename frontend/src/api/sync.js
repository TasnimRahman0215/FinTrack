// /api/v1/sync ("Sync now" and history). Used by features/settings/useConnections.js.
import { http } from './client'

export const syncApi = {
  syncNow: () => http.post('/v1/sync'),
  runs: () => http.get('/v1/sync/runs'),
}
