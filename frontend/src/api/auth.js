// /api/v1/auth. Used by context/AuthContext.jsx and the login/signup pages.
import { http } from './client'

export const authApi = {
  config: () => http.get('/v1/auth/config'),
  me: () => http.get('/v1/auth/me'),
  signup: (data) => http.post('/v1/auth/signup', data),
  login: (data) => http.post('/v1/auth/login', data),
  logout: () => http.post('/v1/auth/logout'),
  // Ends every session of this user, on every device (this one too).
  logoutAll: () => http.post('/v1/auth/logout-all'),
  // { current_password, new_password }. Other sessions are signed out; this one stays.
  changePassword: (data) => http.post('/v1/auth/password', data),
}
