import type { ReactNode } from 'react'
import { errorMessage } from '../hooks/useAtlasQueries'

export function Skeleton({ className = 'h-24' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-slate-200 ${className}`} aria-hidden />
}

export function LoadingBlock({ label = 'Carregando dados da API…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <p className="text-sm text-slate-600">{label}</p>
      <Skeleton className="h-16" />
      <Skeleton className="h-40" />
    </div>
  )
}

export function ErrorBlock({ error }: { error: unknown }) {
  return (
    <div role="alert" aria-live="assertive" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-medium">Não foi possível carregar estes dados.</p>
      <p className="mt-1">{errorMessage(error)}</p>
    </div>
  )
}

export function EmptyBlock({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600">
      {children}
    </div>
  )
}
