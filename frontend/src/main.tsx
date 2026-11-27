import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { createQueryClient } from './api/queryClient'
import { AuthProvider } from './auth/AuthProvider'
import { createAppRouter } from './routes/router'

import 'bootstrap/dist/css/bootstrap.min.css'
import './index.css'

const queryClient = createQueryClient()
const router = createAppRouter()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
