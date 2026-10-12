import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { RankingRow } from '../api/types'
import { CandidatePhoto } from '../components/CandidatePhoto'
import { Filters } from '../components/Filters'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { Button } from '../components/Ui'
import { POLLS_PAGE_SIZE, useOffices, usePollStats, useRanking, useRegisteredPolls } from '../hooks/useAtlasQueries'
import { PollDetailView } from './PollDetailPage'
import { useScopeParams } from '../hooks/useScopeParams'
import { formatDateTime, formatInt, formatPctShort } from '../lib/format'
import { scopeSearch } from '../lib/scopeLinks'
import { canFetchResults, needsUf } from '../lib/scope'

type Janela = '1' | '2'

function isRunoff(row: RankingRow) {
  return Boolean(row.ds_sit_tot_turno && /2/.test(row.ds_sit_tot_turno) && /turno/i.test(row.ds_sit_tot_turno))
}

function CandidateCount({
  rows,
  ano,
  title,
  note,
}: {
  rows: RankingRow[]
  ano: number
  title: string
  note: string
}) {
  const chart = rows.map((row) => ({
    name: row.label,
    votos: row.qt_votos_validos,
    fill: row.color || '#16325c',
  }))
  return (
    <section className="min-w-0 space-y-3 overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <p className="text-sm text-slate-600">{note}</p>
      {chart.length === 0 ? (
        <EmptyBlock>Ainda não há candidaturas neste recorte.</EmptyBlock>
      ) : (
        <div className="h-72 min-w-0" aria-hidden>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fontSize: 10 }}
                tickFormatter={(value: string) => (value.length > 16 ? `${value.slice(0, 15)}…` : value)}
              />
              <Tooltip formatter={(value) => formatInt(Number(value))} />
              <Bar dataKey="votos">
                {chart.map((row) => (
                  <Cell key={row.name} fill={row.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <ol className="space-y-2">
        {rows.map((row) => (
          <li key={row.option_id} className="flex min-w-0 items-center gap-3">
            <span className="inline-block h-3 w-3 shrink-0 rounded-sm ring-1 ring-slate-300" style={{ background: row.color || '#94a3b8' }} aria-hidden />
            <CandidatePhoto
              name={row.label}
              ano={ano}
              cdEleicao={row.cd_eleicao}
              sgUe={row.sg_ue}
              sqCandidato={row.sq_candidato}
              color={row.color}
              size={36}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-atlas-900">
                {row.nr_votavel} {row.label}
              </p>
              <p className="text-xs text-slate-600">
                {row.sg_partido ?? 's/ partido'} · {formatInt(row.qt_votos_validos)} votos válidos · {formatPctShort(row.pct_validos)}
              </p>
            </div>
            {row.ds_sit_tot_turno && (
              <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                {row.ds_sit_tot_turno}
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}

export default function PollsPage() {
  const { scope } = useScopeParams()
  const [params, setParams] = useSearchParams()
  const janela: Janela = params.get('janela') === '1' ? '1' : '2'
  const page = Math.max(1, Number.parseInt(params.get('p') || '1', 10) || 1)
  const ficha = params.get('ficha') || ''

  function patchParams(mutate: (copy: URLSearchParams) => void) {
    const copy = new URLSearchParams(params)
    mutate(copy)
    setParams(copy, { replace: true })
  }

  function setJanela(next: Janela) {
    patchParams((copy) => {
      if (next === '2') copy.delete('janela')
      else copy.set('janela', next)
      copy.delete('p')
      copy.delete('ficha')
    })
  }

  function setPage(next: number) {
    patchParams((copy) => {
      if (next <= 1) copy.delete('p')
      else copy.set('p', String(next))
      copy.delete('ficha')
    })
  }

  function closeFicha() {
    patchParams((copy) => copy.delete('ficha'))
  }

  const offices = useOffices()
  const cargoLabel = offices.data?.data.find((item) => item.cd_cargo === scope.cargo)?.ds_cargo
  const stats = usePollStats(cargoLabel, scope.uf, janela)
  const polls = useRegisteredPolls(cargoLabel, scope.uf, janela, page)
  const ranking = useRanking({ ...scope, turno: 1, municipio: '' }, 'candidatura', 1, 12)
  const ready = canFetchResults({ ...scope, municipio: '', turno: 1 })
  const rows = polls.data?.data ?? []
  const total = polls.data?.meta.pagination?.total ?? 0
  const pageSize = polls.data?.meta.pagination?.page_size ?? POLLS_PAGE_SIZE
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  const listSearch = (protocolo: string) =>
    `/evolucao${scopeSearch(scope, { janela, ficha: protocolo, p: page > 1 ? String(page) : '' })}`
  const candidacies = ranking.data?.data.filter((row) => row.kind === 'candidatura') ?? []
  const runoff = candidacies.filter(isRunoff)
  const officialRows = janela === '2' ? runoff : candidacies.slice(0, 8)
  const series = useMemo(
    () => (stats.data?.data.por_mes ?? []).map((row) => ({ mes: row.mes, n: row.n, amostra: row.amostra })),
    [stats.data],
  )
  const institutes = useMemo(
    () => (stats.data?.data.institutos_top ?? []).map((row) => ({ name: row.instituto, n: row.n })),
    [stats.data],
  )

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Pesquisas registradas</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Clique num protocolo para abrir a ficha, a cobertura pública (quem a imprensa diz que a pesquisa apontou) e, no
          1º turno, o confronto com a urna. O cadastro do TSE <strong>não traz percentuais</strong>; os números da ficha
          vêm das matérias encontradas. 1º e 2º turno não se misturam — o 2º já pode ser aberto mesmo sem urna publicada.
        </p>
      </div>
      <Filters />
      <div className="flex flex-wrap gap-2">
        <Button variant={janela === '1' ? 'primary' : 'secondary'} onClick={() => setJanela('1')}>
          1º turno
        </Button>
        <Button variant={janela === '2' ? 'primary' : 'secondary'} onClick={() => setJanela('2')}>
          2º turno
        </Button>
      </div>
      {!ready && needsUf(scope.cargo) && <EmptyBlock>Para este cargo informe a UF.</EmptyBlock>}
      {stats.isPending && <LoadingBlock label="Carregando registros…" />}
      {stats.isError && <ErrorBlock error={stats.error} />}
      {stats.data && (
        <>
          <div className="grid min-w-0 gap-3 md:grid-cols-3">
            <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Registros nesta janela</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-atlas-900">{formatInt(stats.data.data.total)}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Institutos</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-atlas-900">{formatInt(stats.data.data.institutos)}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Amostra somada</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-atlas-900">{formatInt(stats.data.data.amostra)}</p>
              <p className="mt-1 text-xs text-slate-500">Soma das amostras declaradas — não é eleitorado.</p>
            </article>
          </div>
          <p className="text-sm text-slate-600">
            {janela === '2'
              ? `Coletas que começam depois de ${stats.data.data.dt_primeiro_turno ?? 'a data do 1º turno'}. O 2º turno está marcado para ${stats.data.data.dt_segundo_turno ?? 'data ainda não informada na base'}.`
              : `Coletas encerradas até ${stats.data.data.dt_primeiro_turno ?? 'a data do 1º turno'}.`}
          </p>
          {series.length > 0 ? (
            <div className="h-64 min-w-0 rounded-2xl border border-slate-200 bg-white p-3">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="mes" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Line type="linear" dataKey="n" name="Registros divulgados" stroke="#16325c" dot strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyBlock>Nenhum registro com data nesta janela.</EmptyBlock>
          )}
          {institutes.length > 0 && (
            <div className="h-72 min-w-0 rounded-2xl border border-slate-200 bg-white p-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={institutes} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={160}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(value: string) => (value.length > 22 ? `${value.slice(0, 21)}…` : value)}
                  />
                  <Tooltip />
                  <Bar dataKey="n" name="Registros" fill="#16325c" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
      {ranking.isPending && ready && <LoadingBlock label="Carregando resultado oficial…" />}
      {ranking.isError && ready && <ErrorBlock error={ranking.error} />}
      {ready && ranking.data && (
        <CandidateCount
          rows={officialRows}
          ano={scope.ano}
          title={janela === '2' ? 'Quem vai ao 2º turno (urna do 1º)' : 'Contagem oficial do 1º turno'}
          note={
            janela === '2'
              ? 'Situação 2º TURNO vem do TSE. Os votos abaixo são do 1º turno. O arquivo do 2º turno ainda não foi publicado — sem percentual de pesquisa e sem urna do 2º.'
              : 'Votos válidos oficiais do TSE, cada barra na cor da candidatura. Isto não é pesquisa.'
          }
        />
      )}
      {janela === '2' && ready && ranking.data && runoff.length === 0 && (
        <EmptyBlock>Nenhuma candidatura com situação oficial de 2º turno neste recorte.</EmptyBlock>
      )}
      {polls.isError && <ErrorBlock error={polls.error} />}
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
        {ficha ? (
          <PollDetailView protocolo={ficha} onBack={closeFicha} />
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Escolha uma pesquisa</h2>
                <p className="text-sm text-slate-600">
                  {total === 0
                    ? 'Nenhum registro nesta janela.'
                    : `Mostrando ${from}–${to} de ${formatInt(total)} · ${pageSize} por página.`}
                </p>
              </div>
              {totalPages > 1 && (
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="secondary" onClick={() => setPage(page - 1)} disabled={page <= 1 || polls.isFetching}>
                    Anterior
                  </Button>
                  <p className="text-sm tabular-nums text-slate-700">
                    Página {page} de {totalPages}
                  </p>
                  <Button
                    variant="secondary"
                    onClick={() => setPage(page + 1)}
                    disabled={page >= totalPages || polls.isFetching}
                  >
                    Seguinte
                  </Button>
                </div>
              )}
            </div>
            {polls.isPending && !polls.data ? (
              <LoadingBlock label="Carregando tabela de protocolos…" />
            ) : rows.length === 0 ? (
              <EmptyBlock>Nenhum registro nesta janela para o recorte.</EmptyBlock>
            ) : (
              <div className={`overflow-x-auto rounded-xl border border-slate-200 bg-white ${polls.isFetching ? 'opacity-60' : ''}`}>
                <table className="min-w-[52rem] text-left text-sm">
                  <caption className="sr-only">Pesquisas registradas no TSE, página {page}</caption>
                  <thead className="text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-2 py-2">Protocolo</th>
                      <th className="px-2 py-2">Instituto</th>
                      <th className="px-2 py-2">Cargo / UE</th>
                      <th className="px-2 py-2">Coleta</th>
                      <th className="px-2 py-2">Divulgação</th>
                      <th className="px-2 py-2">Amostra</th>
                      <th className="px-2 py-2"><span className="sr-only">Abrir ficha</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((poll) => (
                      <tr key={poll.nr_protocolo_registro} className="border-t border-slate-100 hover:bg-atlas-50">
                        <td className="px-2 py-1.5 tabular-nums">
                          <Link className="font-medium text-atlas-800 underline" to={listSearch(poll.nr_protocolo_registro)}>
                            {poll.nr_protocolo_registro}
                          </Link>
                        </td>
                        <td className="px-2 py-1.5">
                          <Link className="text-slate-800 hover:underline" to={listSearch(poll.nr_protocolo_registro)}>
                            {poll.nm_empresa} {poll.nm_empresa_fantasia ? `(${poll.nm_empresa_fantasia})` : ''}
                          </Link>
                        </td>
                        <td className="px-2 py-1.5">
                          {poll.ds_cargo} · {poll.sg_uf} {poll.nm_ue}
                        </td>
                        <td className="px-2 py-1.5">
                          {formatDateTime(poll.dt_inicio_pesquisa)} – {formatDateTime(poll.dt_fim_pesquisa)}
                        </td>
                        <td className="px-2 py-1.5">{formatDateTime(poll.dt_divulgacao)}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatInt(poll.qt_entrevistado)}</td>
                        <td className="px-2 py-1.5">
                          <Link className="font-medium text-atlas-800 underline" to={listSearch(poll.nr_protocolo_registro)}>
                            Abrir
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {totalPages > 1 && (
              <div className="flex flex-wrap items-center justify-end gap-2">
                <Button variant="secondary" onClick={() => setPage(page - 1)} disabled={page <= 1 || polls.isFetching}>
                  Anterior
                </Button>
                <p className="text-sm tabular-nums text-slate-700">
                  Página {page} de {totalPages}
                </p>
                <Button variant="secondary" onClick={() => setPage(page + 1)} disabled={page >= totalPages || polls.isFetching}>
                  Seguinte
                </Button>
              </div>
            )}
          </>
        )}
        <p className="text-sm">
          <Link className="text-atlas-700 underline" to={`/pesquisa${scopeSearch(scope, { aba: 'pesquisas' })}`}>
            Buscar um protocolo ou instituto
          </Link>
          {' · '}
          <a
            className="text-atlas-700 underline"
            href="https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas"
            rel="noopener noreferrer nofollow"
            target="_blank"
          >
            Consulta PesqEle (TSE, nova aba)
          </a>
        </p>
      </section>
    </div>
  )
}
