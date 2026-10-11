import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { EnvelopeMeta, RankingRow } from '../api/types'
import { formatInt, formatPctShort } from '../lib/format'
import { isProportional } from '../lib/scope'

export function Ranking({
  rows,
  cargo,
  meta,
  kind,
  onKindChange,
  csvHref,
}: {
  rows: RankingRow[]
  cargo: string
  meta?: EnvelopeMeta
  kind: 'candidatura' | 'todas'
  onKindChange: (kind: 'candidatura' | 'todas') => void
  csvHref: string
}) {
  const proportional = isProportional(cargo)
  const candidacies = rows.filter((row) => row.kind === 'candidatura')
  const chartRows = candidacies.slice(0, 12).map((row) => ({
    name: row.label,
    votos: row.qt_votos_validos,
    fill: row.color || '#1d4ed8',
  }))

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">Ranking</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <label className="inline-flex items-center gap-1">
            <input type="radio" name="kind" checked={kind === 'candidatura'} onChange={() => onKindChange('candidatura')} />
            Somente candidaturas
          </label>
          <label className="inline-flex items-center gap-1">
            <input type="radio" name="kind" checked={kind === 'todas'} onChange={() => onKindChange('todas')} />
            Incluir branco, nulo e legenda
          </label>
          <a className="rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-50" href={csvHref}>
            Exportar CSV
          </a>
        </div>
      </div>
      <p className="text-xs text-slate-600">
        % dos votos válidos = votos válidos da opção / {String(meta?.denominators?.pct_validos ?? 'qt_total_votos_validos')}.
        {proportional && ' Nos cargos proporcionais também se exibe % dos nominais.'}
      </p>
      {chartRows.length > 0 && (
        <div className="h-72" aria-hidden>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartRows} layout="vertical" margin={{ left: 16, right: 16 }}>
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => formatInt(Number(value))} />
              <Bar dataKey="votos" fill="#1d4ed8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <caption className="sr-only">Ranking de opções do recorte</caption>
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-2 py-2">Pos.</th>
              <th className="px-2 py-2">Número</th>
              <th className="px-2 py-2">Nome</th>
              <th className="px-2 py-2">Partido</th>
              <th className="px-2 py-2">Tipo</th>
              <th className="px-2 py-2">Votos válidos</th>
              <th className="px-2 py-2">% dos votos válidos</th>
              {proportional && <th className="px-2 py-2">% dos nominais</th>}
              <th className="px-2 py-2">Situação oficial (TSE)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const notCandidacy = row.kind !== 'candidatura'
              return (
                <tr
                  key={row.option_id}
                  className={notCandidacy ? 'bg-slate-50 italic text-slate-600' : 'text-slate-800'}
                >
                  <td className="px-2 py-1.5 tabular-nums">{row.rank ?? '—'}</td>
                  <td className="px-2 py-1.5 tabular-nums">{row.nr_votavel}</td>
                  <td className="px-2 py-1.5">
                    <span className="inline-flex items-center gap-2">
                      {row.color && (
                        <span className="inline-block h-3 w-3 rounded-sm" style={{ background: row.color }} aria-hidden />
                      )}
                      {row.label}
                    </span>
                  </td>
                  <td className="px-2 py-1.5">{row.sg_partido ?? '—'}</td>
                  <td className="px-2 py-1.5">{row.kind}</td>
                  <td className="px-2 py-1.5 tabular-nums">{formatInt(row.qt_votos_validos)}</td>
                  <td className="px-2 py-1.5 tabular-nums">{formatPctShort(row.pct_validos)}</td>
                  {proportional && <td className="px-2 py-1.5 tabular-nums">{formatPctShort(row.pct_nominais)}</td>}
                  <td className="px-2 py-1.5">{row.ds_sit_tot_turno ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
