import type { EnvelopeMeta } from '../api/types'
import { formatDateTime } from '../lib/format'
import { CoverageBadge } from './CoverageBadge'

export function SourceMeta({ meta }: { meta?: EnvelopeMeta }) {
  if (!meta) return null
  const generated = formatDateTime(meta.source?.source_generated_at)
  const imported = formatDateTime(meta.source?.imported_at)
  return (
    <aside className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700">
      <p>
        <span className="font-medium text-slate-900">Gerado pelo TSE em</span> {generated}
      </p>
      <p>
        <span className="font-medium text-slate-900">Importado em</span> {imported}
      </p>
      {meta.source?.resources && meta.source.resources.length > 0 && (
        <p className="text-xs text-slate-500">Fontes: {meta.source.resources.join(', ')}</p>
      )}
      <CoverageBadge coverage={meta.coverage} />
      {meta.notes?.map((note) => (
        <p key={note} className="text-xs text-slate-600">
          {note}
        </p>
      ))}
    </aside>
  )
}
