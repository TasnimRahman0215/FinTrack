// /api/v1/sync ("Sync now" and history). Used by features/settings/useConnections.js.
// syncNow() only starts the syncs: it resolves to { started: [ids], skipped: [{ connection_id, reason }] }.
import { http } from './client'

export const syncApi = {
  syncNow: () => http.post('/v1/sync'),
  runs: () => http.get('/v1/sync/runs'),
}
