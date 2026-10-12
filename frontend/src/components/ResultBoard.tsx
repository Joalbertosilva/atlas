import { useQueryClient } from '@tanstack/react-query'
import type { RankingRow, Summary } from '../api/types'
import { formatInt, formatPctShort } from '../lib/format'
import { CandidatePhoto } from './CandidatePhoto'
import { Button } from './Ui'

function Bar({ value, color }: { value: number | null | undefined; color: string }) {
  const width = Math.max(0, Math.min(100, value ?? 0))
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-200" aria-hidden>
      <div className="h-full rounded-full" style={{ width: `${width}%`, background: color }} />
    </div>
  )
}

function sitBadge(label: string | null) {
  if (!label) return null
  const second = /2/i.test(label) && /turno/i.test(label)
  return (
    <span
      className={`inline-flex shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        second ? 'bg-atlas-100 text-atlas-800' : 'bg-slate-100 text-slate-700'
      }`}
    >
      {label}
    </span>
  )
}

function CandidateCard({
  row,
  featured,
  ano,
}: {
  row: RankingRow
  featured?: boolean
  ano: number
}) {
  return (
    <article
      className={`flex min-w-0 overflow-hidden gap-3 rounded-2xl border bg-white p-4 ${
        featured ? 'shadow-sm' : 'border-slate-200'
      }`}
      style={{ borderColor: row.color || (featured ? '#16325c' : undefined), borderLeftWidth: 6 }}
    >
      <CandidatePhoto
        name={row.label}
        ano={ano}
        cdEleicao={row.cd_eleicao}
        sgUe={row.sg_ue}
        sqCandidato={row.sq_candidato}
        color={row.color}
        size={featured ? 72 : 52}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {row.sg_partido ?? 's/ partido'} — {row.nr_votavel}
            </p>
            <h3 className={`mt-1 truncate font-semibold text-atlas-900 ${featured ? 'text-lg' : 'text-sm'}`}>{row.label}</h3>
          </div>
          {sitBadge(row.ds_sit_tot_turno)}
        </div>
        <p className={`mt-3 font-semibold tabular-nums text-atlas-900 ${featured ? 'text-3xl' : 'text-xl'}`}>
          {formatPctShort(row.pct_validos)}
        </p>
        <p className="mt-1 text-sm tabular-nums text-slate-600">{formatInt(row.qt_votos_validos)} votos válidos</p>
        <div className="mt-3">
          <Bar value={row.pct_validos} color={row.color || '#16325c'} />
        </div>
      </div>
    </article>
  )
}

export function ResultBoard({
  summary,
  ranking,
  cargoLabel,
  ano,
}: {
  summary: Summary
  ranking: RankingRow[]
  cargoLabel: string
  ano: number
}) {
  const queryClient = useQueryClient()
  const candidacies = ranking.filter((row) => row.kind === 'candidatura')
  const top = candidacies.slice(0, 2)
  const rest = candidacies.slice(2, 6)
  const votos = summary.qt_votos || 0
  const pctNominais = votos ? (100 * summary.qt_votos_nominais_validos) / votos : 0
  const secoes = summary.qt_total_secoes

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
      <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="inline-flex rounded-md bg-atlas-700 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white">
          {cargoLabel}
        </p>
        <h2 className="mt-3 text-sm font-semibold text-slate-900">Dados gerais</h2>
        <dl className="mt-3 space-y-3 text-sm">
          {secoes != null && (
            <div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Seções totalizadas</dt>
                <dd className="tabular-nums font-medium">{formatInt(secoes)}</dd>
              </div>
            </div>
          )}
          <div>
            <div className="flex justify-between gap-2">
              <dt className="text-slate-500">Eleitores aptos</dt>
              <dd className="tabular-nums font-medium">{formatInt(summary.qt_aptos)}</dd>
            </div>
          </div>
          <div>
            <div className="mb-1 flex justify-between gap-2">
              <dt className="text-slate-500">Comparecimento</dt>
              <dd className="tabular-nums font-medium">{formatPctShort(summary.pct_comparecimento)}</dd>
            </div>
            <Bar value={summary.pct_comparecimento} color="#16325c" />
          </div>
          <div>
            <div className="mb-1 flex justify-between gap-2">
              <dt className="text-slate-500">Votos nominais</dt>
              <dd className="tabular-nums font-medium">{formatPctShort(pctNominais)}</dd>
            </div>
            <Bar value={pctNominais} color="#1d4ed8" />
          </div>
          <div>
            <div className="mb-1 flex justify-between gap-2">
              <dt className="text-slate-500">Válidos</dt>
              <dd className="tabular-nums font-medium">{formatInt(summary.qt_total_votos_validos)}</dd>
            </div>
          </div>
          <div>
            <div className="mb-1 flex justify-between gap-2">
              <dt className="text-slate-500">Brancos</dt>
              <dd className="tabular-nums font-medium">{formatPctShort(summary.pct_brancos)}</dd>
            </div>
            <Bar value={summary.pct_brancos} color="#ca8a04" />
          </div>
          <div>
            <div className="mb-1 flex justify-between gap-2">
              <dt className="text-slate-500">Nulos</dt>
              <dd className="tabular-nums font-medium">{formatPctShort(summary.pct_nulos)}</dd>
            </div>
            <Bar value={summary.pct_nulos} color="#7c3aed" />
          </div>
        </dl>
        <p className="mt-4 text-xs text-slate-500">Branco e nulo não são candidaturas. Totais oficiais do TSE.</p>
      </aside>
      <section className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-atlas-700">Candidaturas</p>
          <Button
            variant="secondary"
            onClick={() => {
              void queryClient.invalidateQueries()
            }}
          >
            Atualizar
          </Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {top.map((row) => (
            <CandidateCard key={row.option_id} row={row} featured ano={ano} />
          ))}
        </div>
        {rest.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-2">
            {rest.map((row) => (
              <CandidateCard key={row.option_id} row={row} ano={ano} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
