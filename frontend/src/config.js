// Build-time configuration. Used by api/client.js.
// Base URL for API calls. "/api" (default) means same origin: the Vite dev proxy or nginx
// forwards it to the backend. Set VITE_API_BASE_URL to a full URL to call a remote API.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
