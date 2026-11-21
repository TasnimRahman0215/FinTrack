// App entry point (loaded by index.html). Sets up the providers every page relies on:
// TanStack Query (server data cache) -> router -> auth (current user) -> scope (Me/member/Household).
import './styles/index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import App from './App'
import { AuthProvider } from './context/AuthContext'
import { ScopeProvider } from './context/ScopeContext'

// staleTime: data younger than 30 s is reused without refetching when a page remounts.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      // Don't retry auth/permission/validation errors; do retry flaky network once.
      retry: (failureCount, error) => failureCount < 1 && !(error?.status >= 400 && error?.status < 500),
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ScopeProvider>
            <App />
          </ScopeProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
