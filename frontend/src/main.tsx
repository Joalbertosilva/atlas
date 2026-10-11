import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ApiClientError } from './api/client'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      retry: (count, error) => {
        if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) return false
        return count < 1
      },
    },
  },
})

const root = document.getElementById('root')
if (!root) throw new Error('Elemento #root ausente')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
