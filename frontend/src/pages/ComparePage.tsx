import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CandidatePhoto } from '../components/CandidatePhoto'
import { Filters } from '../components/Filters'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import { Button } from '../components/Ui'
import { useCrossCompare, useRanking } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { formatInt, formatPctShort, formatSigned } from '../lib/format'
import { canFetchResults, needsUf, parseAno, type ScopeState } from '../lib/scope'
import PartyComparePanel from './HistoricoPage'

function setParam(params: URLSearchParams, key: string, value: string) {
  if (!value) params.delete(key)
  else params.set(key, value)
}

function CandidatePicker({
  label,
  ano,
  optionId,
  rankingAno,
  scope,
  onAno,
  onOption,
}: {
  label: string
  ano: 2022 | 2026
  optionId: string
  rankingAno: 2022 | 2026
  scope: ScopeState
  onAno: (ano: 2022 | 2026) => void
  onOption: (id: string) => void
}) {
  const ranking = useRanking({ ...scope, ano: rankingAno, municipio: '', option: '' }, 'candidatura', 1, 80)
  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" aria-label={label}>
      <h2 className="mb-3 text-sm font-semibold text-atlas-900">{label}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Ano</span>
          <select className="field" value={String(ano)} onChange={(event) => onAno(event.target.value === '2022' ? 2022 : 2026)}>
            <option value="2026">2026</option>
            <option value="2022">2022</option>
          </select>
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block font-medium">Candidatura</span>
          {ranking.isPending && <p className="text-xs text-slate-500">Carregando opções de {ano}…</p>}
          {ranking.isError && <ErrorBlock error={ranking.error} />}
          <select className="field" value={optionId} onChange={(event) => onOption(event.target.value)}>
            <option value="">Selecione</option>
            {(ranking.data?.data ?? [])
              .filter((row) => row.kind === 'candidatura')
              .map((row) => (
                <option key={row.option_id} value={String(row.option_id)}>
                  {ano} · {row.nr_votavel} — {row.label} ({row.sg_partido ?? 's/ partido'})
                </option>
              ))}
          </select>
        </label>
      </div>
    </section>
  )
}

export default function ComparePage() {
  const { scope, update } = useScopeParams()
  const [params, setParams] = useSearchParams()
  const painel = params.get('painel') === 'partidos' ? 'partidos' : 'candidaturas'
  const aAno = parseAno(params.get('a_ano') || '2026')
  const bAno = parseAno(params.get('b_ano') || '2022')
  const aOption = params.get('a_option') || ''
  const bOption = params.get('b_option') || ''
  const ready = canFetchResults({ ...scope, municipio: '' })
  const ids = [aOption, bOption].filter(Boolean).join(',')
  const cross = useCrossCompare(scope, aOption && bOption ? `${aOption},${bOption}` : '')

  function patchCompare(next: { painel?: string; a_ano?: string; b_ano?: string; a_option?: string; b_option?: string }) {
    const copy = new URLSearchParams(params)
    if (next.painel !== undefined) setParam(copy, 'painel', next.painel === 'candidaturas' ? '' : next.painel)
    if (next.a_ano !== undefined) setParam(copy, 'a_ano', next.a_ano === '2026' ? '' : next.a_ano)
    if (next.b_ano !== undefined) setParam(copy, 'b_ano', next.b_ano === '2022' ? '' : next.b_ano)
    if (next.a_option !== undefined) setParam(copy, 'a_option', next.a_option)
    if (next.b_option !== undefined) setParam(copy, 'b_option', next.b_option)
    setParams(copy, { replace: true })
  }

  const chartData = useMemo(() => {
    return (cross.data?.data.options ?? []).map((opt) => ({
      name: `${opt.ano} · ${opt.label}`,
      votos: opt.qt_votos_validos,
      pct: opt.pct_validos,
      fill: opt.color || '#16325c',
    }))
  }, [cross.data])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Comparar</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Escolha duas candidaturas de qualquer ano publicado — por exemplo Lula 2026 × Lula 2022, ou Flávio 2026 × Lula
          2022. Cada lado usa os válidos daquele ano. Partido 2022 × 2026 fica na outra aba, neste mesmo recorte.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant={painel === 'candidaturas' ? 'primary' : 'secondary'} onClick={() => patchCompare({ painel: 'candidaturas' })}>
          Candidaturas
        </Button>
        <Button variant={painel === 'partidos' ? 'primary' : 'secondary'} onClick={() => patchCompare({ painel: 'partidos' })}>
          Partidos 2022 × 2026
        </Button>
      </div>
      <Filters />
      {painel === 'partidos' ? (
        <PartyComparePanel embedded />
      ) : (
        <>
          {!ready && needsUf(scope.cargo) && (
            <EmptyBlock>Para comparar este cargo informe a UF no filtro — não existe disputa nacional.</EmptyBlock>
          )}
          <div className="grid gap-3 lg:grid-cols-2">
            <CandidatePicker
              label="Lado A"
              ano={aAno}
              optionId={aOption}
              rankingAno={aAno}
              scope={scope}
              onAno={(ano) => patchCompare({ a_ano: String(ano), a_option: '' })}
              onOption={(id) => patchCompare({ a_option: id })}
            />
            <CandidatePicker
              label="Lado B"
              ano={bAno}
              optionId={bOption}
              rankingAno={bAno}
              scope={scope}
              onAno={(ano) => patchCompare({ b_ano: String(ano), b_option: '' })}
              onOption={(id) => patchCompare({ b_option: id })}
            />
          </div>
          {ids.split(',').filter(Boolean).length < 2 && (
            <EmptyBlock>Selecione uma candidatura em cada lado. Cada ano tem a própria lista — a mesma pessoa em 2022 e 2026 são escolhas distintas.</EmptyBlock>
          )}
          {cross.isPending && aOption && bOption && <LoadingBlock label="Comparando os dois lados…" />}
          {cross.isError && <ErrorBlock error={cross.error} />}
          {cross.data && (
            <>
              <SourceMeta meta={cross.data.meta} />
              <div className="grid gap-3 sm:grid-cols-2">
                {cross.data.data.options.map((opt) => (
                  <article key={opt.option_id} className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <CandidatePhoto
                      name={opt.label}
                      ano={opt.ano}
                      cdEleicao={opt.cd_eleicao}
                      sgUe={opt.sg_ue}
                      sqCandidato={opt.sq_candidato}
                      color={opt.color}
                      size={72}
                    />
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {opt.ano} · {opt.sg_partido ?? 's/ partido'} — {opt.nr_votavel}
                      </p>
                      <h2 className="mt-1 text-lg font-semibold text-atlas-900">{opt.label}</h2>
                      <p className="mt-2 text-3xl font-semibold tabular-nums">{formatPctShort(opt.pct_validos)}</p>
                      <p className="text-sm tabular-nums text-slate-600">
                        {formatInt(opt.qt_votos_validos)} votos válidos de {formatInt(opt.qt_total_votos_validos)}
                      </p>
                      {opt.ds_sit_tot_turno && (
                        <p className="mt-2 text-xs text-slate-500">Situação oficial: {opt.ds_sit_tot_turno}</p>
                      )}
                    </div>
                  </article>
                ))}
              </div>
              <div className="h-72 min-w-0 rounded-2xl border border-slate-200 bg-white p-3" aria-hidden>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis />
                    <Tooltip formatter={(value) => formatInt(Number(value))} />
                    <Legend />
                    <Bar dataKey="votos" name="Votos válidos">
                      {chartData.map((row) => (
                        <Cell key={row.name} fill={row.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
                <table className="min-w-full text-left text-sm">
                  <caption className="sr-only">Comparação territorial dos dois lados</caption>
                  <thead className="text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-2 py-2">{cross.data.data.level === 'uf' ? 'UF' : 'Município'}</th>
                      <th className="px-2 py-2">A % válidos</th>
                      <th className="px-2 py-2">B % válidos</th>
                      <th className="px-2 py-2">Δ pp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cross.data.data.places.slice(0, 200).map((place) => (
                      <tr
                        key={place.place_id}
                        className="cursor-pointer border-t border-slate-100 hover:bg-atlas-50"
                        onClick={() => {
                          if (cross.data?.data.level === 'uf') update({ uf: place.sg_uf, municipio: '' })
                          else if (place.cd_municipio_tse) update({ uf: place.sg_uf, municipio: place.cd_municipio_tse })
                        }}
                      >
                        <td className="px-2 py-1.5">{place.nome} ({place.sg_uf})</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatPctShort(place.a.pct_validos)}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatPctShort(place.b.pct_validos)}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatSigned(place.delta_pp, 'pp')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {cross.data.data.places.length > 200 && (
                <p className="text-xs text-slate-500">Exibindo os 200 primeiros territórios da resposta da API.</p>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
