// /api/v1/household. Used by features/settings/useHousehold.js.
import { http } from './client'

export const householdApi = {
  get: () => http.get('/v1/household'),
  update: (data) => http.patch('/v1/household', data),
}
