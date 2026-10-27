// The single fetch wrapper used by every module in src/api/. It adds the base URL, sends the
// session cookie, adds the CSRF header the backend requires on writes, and turns error
// responses into ApiError with a readable message (shown by components/ui/Feedback.jsx).

import { API_BASE_URL } from '../config'

// Fired when a session expires mid-use; context/AuthContext.jsx listens and signs the UI out.
export const UNAUTHORIZED_EVENT = 'fintrack:unauthorized'

/** An HTTP error. `status` is 0 for network failures; `code` mirrors the backend's error code. */
export class ApiError extends Error {
  constructor(status, message, code) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Pick a human-readable message out of a backend error body. */
function errorMessage(data, status) {
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{ loc: ['body', 'password'], msg: '...' }]
    const { loc = [], msg = 'Invalid value' } = detail[0]
    const field = loc[loc.length - 1]
    return typeof field === 'string' ? `${field.replaceAll('_', ' ')}: ${msg}` : msg
  }
  return `Request failed (${status})`
}

/** Call `${API_BASE_URL}${path}`. Empty params are dropped. Resolves to the JSON body (null for 204). */
export async function request(path, { method = 'GET', body, params, signal } = {}) {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  }

  // X-Requested-With is the CSRF guard: the backend rejects writes without it (see app/main.py).
  const headers = { Accept: 'application/json', 'X-Requested-With': 'fintrack' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(url, {
      method,
      credentials: 'include',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError(0, "Can't reach the FinTrack server. Is the backend running?", 'network')
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    // Auth endpoints return 401 for wrong passwords; only other 401s mean "session expired".
    if (res.status === 401 && !path.startsWith('/v1/auth/')) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    throw new ApiError(res.status, errorMessage(data, res.status), data?.code)
  }
  return data
}

export const http = {
  get: (path, params, opts) => request(path, { ...opts, params }),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
