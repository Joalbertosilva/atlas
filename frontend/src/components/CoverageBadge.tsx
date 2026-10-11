import type { CoverageMeta } from '../api/types'

const STYLES: Record<string, string> = {
  completo: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  parcial: 'bg-amber-50 text-amber-900 ring-amber-200',
  indisponivel: 'bg-red-50 text-red-800 ring-red-200',
  pendente: 'bg-slate-100 text-slate-700 ring-slate-200',
}

export function CoverageBadge({ coverage }: { coverage?: CoverageMeta }) {
  if (!coverage?.status) return null
  const style = STYLES[coverage.status] ?? 'bg-slate-100 text-slate-700 ring-slate-200'
  return (
    <div className="space-y-1">
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}>
        Cobertura: {coverage.status}
        {coverage.published_scopes !== undefined && coverage.expected_scopes !== undefined
          ? ` (${coverage.published_scopes}/${coverage.expected_scopes})`
          : ''}
      </span>
      {coverage.notes?.map((note) => (
        <p key={note} className="text-xs text-slate-600">
          {note}
        </p>
      ))}
    </div>
  )
}
