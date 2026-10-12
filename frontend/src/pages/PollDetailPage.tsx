import { Link, useParams } from 'react-router'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PollConfronto, PollMencao, PollUrnaRow, SearchHit } from '../api/types'
import { CandidatePhoto } from '../components/CandidatePhoto'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { usePollLeitura } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { formatDateTime, formatInt, formatPctShort, formatSigned } from '../lib/format'
import { scopeSearch } from '../lib/scopeLinks'

function isRunoff(row: PollUrnaRow) {
  return Boolean(row.ds_sit_tot_turno && /2/.test(row.ds_sit_tot_turno) && /turno/i.test(row.ds_sit_tot_turno))
}

function PctChart({
  rows,
  valueKey,
}: {
  rows: Array<{ name: string; value: number; fill: string }>
  valueKey: string
}) {
  if (rows.length === 0) return null
  return (
    <div className="h-64 min-w-0" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
          <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
          <Tooltip formatter={(value) => `${Number(value).toLocaleString('pt-BR')}%`} />
          <Bar dataKey={valueKey}>
            {rows.map((row) => (
              <Cell key={row.name} fill={row.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function MentionList({ rows }: { rows: PollMencao[] }) {
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.option_id} className="flex min-w-0 items-start gap-3">
          <span className="mt-1 inline-block h-3 w-3 shrink-0 rounded-sm ring-1 ring-slate-300" style={{ background: row.color || '#94a3b8' }} aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-atlas-900">
              {row.nr_votavel} {row.label} · {formatPctShort(row.pct_mencao)}
            </p>
            {row.trecho && <p className="mt-1 text-xs text-slate-600">“{row.trecho}”</p>}
            {row.fonte_url && (
              <a className="text-xs text-atlas-700 underline" href={row.fonte_url} rel="noopener noreferrer nofollow" target="_blank">
                Abrir matéria
              </a>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

function OfficialList({ rows, ano }: { rows: PollUrnaRow[]; ano: number }) {
  return (
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
            <p className="truncate text-sm font-semibold">{row.nr_votavel} {row.label}</p>
            <p className="text-xs text-slate-600">
              {row.sg_partido ?? 's/ partido'} · {formatInt(row.qt_votos_validos)} · {formatPctShort(row.pct_validos)}
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
  )
}

function HitList({ hits }: { hits: SearchHit[] }) {
  if (hits.length === 0) {
    return <EmptyBlock>Nenhuma matéria pública foi localizada agora para este protocolo. Tente o PesqEle ou outra consulta.</EmptyBlock>
  }
  return (
    <ul className="space-y-3">
      {hits.map((hit) => (
        <li key={hit.url} className="rounded-xl border border-slate-200 bg-white p-3">
          <a className="font-medium text-atlas-800 underline" href={hit.url} rel="noopener noreferrer nofollow" target="_blank">
            {hit.title}
          </a>
          <p className="text-xs text-slate-500">
            {hit.domain}
            {hit.engines?.length ? ` · ${hit.engines.join(', ')}` : ''}
          </p>
          <p className="mt-1 text-sm text-slate-700">{hit.snippet}</p>
        </li>
      ))}
    </ul>
  )
}

function ConfrontoTable({ rows }: { rows: PollConfronto[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="min-w-[36rem] text-left text-sm">
        <caption className="sr-only">Cobertura da pesquisa versus urna do 1º turno</caption>
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">Candidatura</th>
            <th className="px-3 py-2">Citado na cobertura</th>
            <th className="px-3 py-2">Urna 1º turno</th>
            <th className="px-3 py-2">Δ pp</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.option_id} className="border-t border-slate-100">
              <td className="px-3 py-2">
                <span className="inline-flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-sm ring-1 ring-slate-300" style={{ background: row.color || '#94a3b8' }} aria-hidden />
                  {row.nr_votavel} {row.label}
                </span>
              </td>
              <td className="px-3 py-2 tabular-nums">{formatPctShort(row.pct_mencao)}</td>
              <td className="px-3 py-2 tabular-nums">{formatPctShort(row.pct_urna)}</td>
              <td className="px-3 py-2 tabular-nums">{formatSigned(row.delta_pp, 'pp')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PollDetailView({
  protocolo,
  onBack,
}: {
  protocolo: string
  onBack?: () => void
}) {
  const { scope } = useScopeParams()
  const leitura = usePollLeitura(protocolo, scope.cargo)
  const data = leitura.data?.data
  const poll = data?.poll
  const janela = data?.janela
  const ano = scope.ano
  const urna = data?.urna ?? []
  const urnaView = janela === '2' ? urna.filter(isRunoff) : urna.slice(0, 8)
  const mencoes = data?.mencoes ?? []
  const back = `/evolucao${scopeSearch(scope, janela ? { janela } : {})}`

  return (
    <div className="space-y-5">
      <p>
        {onBack ? (
          <button type="button" className="text-sm text-atlas-700 underline" onClick={onBack}>
            Voltar à lista
          </button>
        ) : (
          <Link className="text-sm text-atlas-700 underline" to={back}>
            Voltar às pesquisas
          </Link>
        )}
      </p>
      {leitura.isPending && <LoadingBlock label="Abrindo a pesquisa e a cobertura pública…" />}
      {leitura.isError && <ErrorBlock error={leitura.error} />}
      {poll && (
        <>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {janela === '2' ? 'Pesquisa de 2º turno' : janela === '1' ? 'Pesquisa de 1º turno' : 'Pesquisa registrada'}
            </p>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">
              {poll.nm_empresa_fantasia || poll.nm_empresa} · {poll.nr_protocolo_registro}
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Ficha oficial do TSE (cadastro, sem percentuais). Os números de intenção de voto, se aparecerem, vêm de
              matérias públicas localizadas agora — abra a fonte. Consulta feita pelo nosso servidor, sem guardar o texto
              da busca.
            </p>
          </div>
          <dl className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase text-slate-500">Instituto</dt>
              <dd>{poll.nm_empresa} {poll.nm_empresa_fantasia ? `(${poll.nm_empresa_fantasia})` : ''}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Cargo / UE</dt>
              <dd>{poll.ds_cargo} · {poll.sg_uf} {poll.nm_ue}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Coleta</dt>
              <dd>{formatDateTime(poll.dt_inicio_pesquisa)} – {formatDateTime(poll.dt_fim_pesquisa)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Divulgação</dt>
              <dd>{formatDateTime(poll.dt_divulgacao)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Amostra</dt>
              <dd>{formatInt(poll.qt_entrevistado)} entrevistados</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">PesqEle</dt>
              <dd>
                <a className="text-atlas-700 underline" href={poll.pesqele_url ?? undefined} rel="noopener noreferrer nofollow" target="_blank">
                  Consultar protocolo {poll.nr_protocolo_registro}
                </a>
              </dd>
            </div>
            {poll.ds_metodologia_pesquisa && (
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase text-slate-500">Metodologia (cadastro TSE)</dt>
                <dd className="mt-1 whitespace-pre-wrap text-slate-700">{poll.ds_metodologia_pesquisa}</dd>
              </div>
            )}
          </dl>
          <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-base font-semibold">O que a cobertura diz</h2>
            <p className="text-sm text-slate-600">
              Percentuais extraídos só quando o trecho cita uma candidatura oficial ao lado de um número com %. Sem
              citação, a lista fica vazia — a matéria original continua abaixo.
            </p>
            {mencoes.length > 0 ? (
              <>
                <PctChart
                  rows={mencoes.map((row) => ({ name: row.label, value: row.pct_mencao, fill: row.color || '#16325c' }))}
                  valueKey="value"
                />
                <MentionList rows={mencoes} />
              </>
            ) : (
              <EmptyBlock>A cobertura encontrada não trouxe percentuais casáveis com as candidaturas oficiais.</EmptyBlock>
            )}
          </section>
          <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-base font-semibold">
              {janela === '2' ? 'Urna do 1º turno (quem foi ao 2º)' : 'Urna oficial do 1º turno'}
            </h2>
            <p className="text-sm text-slate-600">
              {janela === '2'
                ? 'O arquivo do 2º turno ainda não foi publicado. Abaixo está o resultado oficial do 1º para as candidaturas que o TSE marcou como 2º TURNO.'
                : 'Resultado oficial do TSE no mesmo cargo e território da pesquisa. Serve para comparar com o que a cobertura atribuiu a este instituto.'}
            </p>
            {urnaView.length > 0 ? (
              <>
                <PctChart
                  rows={urnaView.filter((row) => row.pct_validos != null).map((row) => ({
                    name: row.label,
                    value: row.pct_validos as number,
                    fill: row.color || '#16325c',
                  }))}
                  valueKey="value"
                />
                <OfficialList rows={urnaView} ano={ano} />
              </>
            ) : (
              <EmptyBlock>Resultado oficial indisponível para este recorte.</EmptyBlock>
            )}
          </section>
          {janela === '1' && data?.confronto && data.confronto.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-base font-semibold">Acertos da cobertura × urna</h2>
              <p className="text-sm text-slate-600">
                Δ pp = pontos percentuais citados na matéria menos o % de válidos na urna. Não é o relatório confidencial
                do instituto; é o que a imprensa publicou sobre esta pesquisa.
              </p>
              <ConfrontoTable rows={data.confronto} />
            </section>
          )}
          <section className="space-y-3">
            <h2 className="text-base font-semibold">Matérias encontradas</h2>
            {(leitura.data?.meta.notes ?? []).map((note) => (
              <p key={note} className="text-xs text-slate-500">{note}</p>
            ))}
            <HitList hits={data?.hits ?? []} />
          </section>
        </>
      )}
    </div>
  )
}

export default function PollDetailPage() {
  const { protocolo } = useParams()
  if (!protocolo) return null
  return <PollDetailView protocolo={protocolo} />
}
