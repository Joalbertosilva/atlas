import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { EnvelopeMeta, RankingRow } from '../api/types'
import { formatInt, formatPctShort, kindLabel } from '../lib/format'
import { isProportional } from '../lib/scope'
import { CandidatePhoto } from './CandidatePhoto'

export function Ranking({
  rows,
  cargo,
  ano,
  kind,
  onKindChange,
  csvHref,
}: {
  rows: RankingRow[]
  cargo: string
  ano: number
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
    <section className="min-w-0 space-y-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">Ranking</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5">
            <input type="radio" name="kind" checked={kind === 'candidatura'} onChange={() => onKindChange('candidatura')} />
            Somente candidaturas
          </label>
          <label className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5">
            <input type="radio" name="kind" checked={kind === 'todas'} onChange={() => onKindChange('todas')} />
            Incluir branco, nulo e legenda
          </label>
          <a className="btn btn-secondary !min-h-9 !px-3 !py-1.5" href={csvHref}>
            Exportar CSV
          </a>
        </div>
      </div>
      <p className="text-xs text-slate-600">
        Porcentagem sobre o total de votos válidos deste recorte.
        {proportional && ' Nos cargos proporcionais também se exibe a fatia dos votos nominais.'}
      </p>
      {chartRows.length > 0 && (
        <div className="h-72 min-w-0" aria-hidden>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartRows} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                width={108}
                tick={{ fontSize: 10 }}
                tickFormatter={(value: string) => (value.length > 14 ? `${value.slice(0, 13)}…` : value)}
              />
              <Tooltip formatter={(value) => formatInt(Number(value))} />
              <Bar dataKey="votos">
                {chartRows.map((row) => (
                  <Cell key={row.name} fill={row.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-[44rem] text-left text-sm">
          <caption className="sr-only">Ranking de opções do recorte</caption>
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              <th className="whitespace-nowrap px-2 py-2">Pos.</th>
              <th className="whitespace-nowrap px-2 py-2">Número</th>
              <th className="whitespace-nowrap px-2 py-2">Nome</th>
              <th className="whitespace-nowrap px-2 py-2">Partido</th>
              <th className="whitespace-nowrap px-2 py-2">Tipo</th>
              <th className="whitespace-nowrap px-2 py-2">Votos válidos</th>
              <th className="whitespace-nowrap px-2 py-2">% dos votos válidos</th>
              {proportional && <th className="whitespace-nowrap px-2 py-2">% dos nominais</th>}
              <th className="whitespace-nowrap px-2 py-2">Situação oficial (TSE)</th>
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
                    <span className="inline-flex min-w-0 max-w-[16rem] items-center gap-2">
                      {row.kind === 'candidatura' ? (
                        <CandidatePhoto
                          name={row.label}
                          ano={ano}
                          cdEleicao={row.cd_eleicao}
                          sgUe={row.sg_ue}
                          sqCandidato={row.sq_candidato}
                          color={row.color}
                          size={28}
                        />
                      ) : (
                        row.color && (
                          <span className="inline-block h-3 w-3 rounded-sm" style={{ background: row.color }} aria-hidden />
                        )
                      )}
                      <span className="min-w-0 truncate">{row.label}</span>
                    </span>
                  </td>
                  <td className="px-2 py-1.5">{row.sg_partido ?? '—'}</td>
                  <td className="px-2 py-1.5">{kindLabel(row.kind)}</td>
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
