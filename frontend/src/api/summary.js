// /api/v1/summary (dashboard totals). Used by features/dashboard/useSummary.js.
import { http } from './client'

export const summaryApi = {
  get: ({ scope }) => http.get('/v1/summary', { scope }),
}
