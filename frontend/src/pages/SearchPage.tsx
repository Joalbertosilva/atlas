import { useMemo, useState, type FormEvent } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { searchPost } from '../api/client'
import type { Envelope, RegisteredPoll, SearchHit } from '../api/types'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { formatDateTime, formatTime } from '../lib/format'

type Tab = 'web' | 'news' | 'pesquisas' | 'checagens'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'news', label: 'Notícias' },
  { id: 'web', label: 'Web' },
  { id: 'pesquisas', label: 'Pesquisas registradas' },
  { id: 'checagens', label: 'Checagens' },
]

function tabFromAba(aba: string | null): Tab {
  if (aba === 'web' || aba === 'news' || aba === 'pesquisas' || aba === 'checagens') return aba
  if (aba === 'noticias') return 'news'
  return 'news'
}

function factCheckLabel(status?: string, metaStatus?: string) {
  if (metaStatus === 'sem_correspondencia_suficiente') return 'Sem correspondência suficiente'
  if (metaStatus === 'fonte_temporariamente_indisponivel') return 'Fonte temporariamente indisponível'
  if (status === 'checagem_publicada_identificada') return 'Checagem publicada identificada'
  if (status === 'possivel_checagem_relacionada') return 'Possível checagem relacionada'
  return status || metaStatus || 'Resultado'
}

export function SearchPageInner({ forceTab }: { forceTab?: Tab }) {
  const [params, setParams] = useSearchParams()
  const tab = forceTab ?? tabFromAba(params.get('aba'))
  const [q, setQ] = useState('')
  const [uf, setUf] = useState('')
  const [municipio, setMunicipio] = useState('')
  const [candidato, setCandidato] = useState('')
  const [empresa, setEmpresa] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [hits, setHits] = useState<Envelope<SearchHit[]> | Envelope<RegisteredPoll[]> | null>(null)

  function setTab(next: Tab) {
    const usp = new URLSearchParams(params)
    usp.set('aba', next)
    setParams(usp, { replace: true })
    setHits(null)
    setError(null)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (q.trim().length < 2 && tab !== 'pesquisas') return
    setLoading(true)
    setError(null)
    try {
      const body = {
        q: q.trim(),
        page,
        uf: uf || undefined,
        municipio: municipio || undefined,
        candidato: candidato || undefined,
        empresa: empresa || undefined,
      }
      const path =
        tab === 'web'
          ? '/search/web'
          : tab === 'news'
            ? '/search/news'
            : tab === 'checagens'
              ? '/search/fact-checks'
              : '/search/polls'
      let result = await searchPost<SearchHit[] | RegisteredPoll[]>(path, body)
      if (tab === 'news' && Array.isArray(result.data) && result.data.length === 0) {
        const web = await searchPost<SearchHit[]>('/search/web', body)
        if (Array.isArray(web.data) && web.data.length > 0) {
          result = {
            ...web,
            meta: {
              ...web.meta,
              status: web.meta.status === 'ok' ? 'parcial' : web.meta.status,
              providers: [...(result.meta.providers ?? []), ...(web.meta.providers ?? [])],
            },
          }
        }
      }
      setHits(result as Envelope<SearchHit[]> | Envelope<RegisteredPoll[]>)
    } catch (err) {
      setError(err)
      setHits(null)
    } finally {
      setLoading(false)
    }
  }

  const cacheLabel = useMemo(() => {
    const fetched = hits?.meta.cache?.fetched_at
    const time = formatTime(fetched ?? null)
    if (!time) return null
    return `resultado em cache obtido às ${time}`
  }, [hits])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Pesquisa</h1>
      <div className="space-y-2 rounded-lg border border-atlas-100 bg-atlas-50 px-4 py-3">
        <p className="text-base font-semibold text-atlas-800">
          Confirme notícias sobre candidatos. Não caia em fake news.
        </p>
        <p className="text-sm text-slate-700">
          Digite o que quiser — nome, número, fato ou alegação. O Atlas consulta mecanismos públicos (DuckDuckGo, Bing,
          Wikipedia) pelo nosso servidor e devolve título, trecho e o site para você ler a matéria original.
        </p>
        <p className="text-xs text-slate-600">
          Não classificamos verdadeiro ou falso. Não guardamos o texto da sua busca. Evite dado pessoal.
        </p>
      </div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Tipos de busca">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === item.id ? 'bg-atlas-800 text-white' : 'bg-white ring-1 ring-slate-300'}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <form className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2" onSubmit={onSubmit}>
        <label className="sm:col-span-2 text-sm">
          <span className="mb-1 block font-medium">Consulta</span>
          <input
            className="w-full rounded-md border border-slate-300 px-2 py-2"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            minLength={tab === 'pesquisas' ? 0 : 2}
            required={tab !== 'pesquisas'}
            placeholder="Ex.: Lula, Flavio Bolsonaro, pesquisa Ipec 2026"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">UF (contexto, opcional)</span>
          <input className="w-full rounded-md border border-slate-300 px-2 py-2" value={uf} onChange={(event) => setUf(event.target.value.toUpperCase())} maxLength={2} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Município TSE (contexto)</span>
          <input className="w-full rounded-md border border-slate-300 px-2 py-2" value={municipio} onChange={(event) => setMunicipio(event.target.value)} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Candidato (contexto)</span>
          <input className="w-full rounded-md border border-slate-300 px-2 py-2" value={candidato} onChange={(event) => setCandidato(event.target.value)} />
        </label>
        {tab === 'pesquisas' && (
          <label className="text-sm">
            <span className="mb-1 block font-medium">Empresa</span>
            <input className="w-full rounded-md border border-slate-300 px-2 py-2" value={empresa} onChange={(event) => setEmpresa(event.target.value)} />
          </label>
        )}
        <div className="sm:col-span-2 flex items-center gap-3">
          <button type="submit" className="rounded-md bg-atlas-800 px-3 py-2 text-sm text-white">
            Buscar
          </button>
          <label className="text-sm">
            Página
            <input
              className="ml-2 w-16 rounded-md border border-slate-300 px-2 py-1"
              type="number"
              min={1}
              max={5}
              value={page}
              onChange={(event) => setPage(Number(event.target.value) || 1)}
            />
          </label>
        </div>
      </form>
      <div aria-live="polite">
        {loading && <LoadingBlock label="Consultando…" />}
        {error !== null && <ErrorBlock error={error} />}
      </div>
      {hits && (
        <div className="space-y-3">
          {cacheLabel && hits.meta.cache?.hit && <p className="text-xs text-slate-500">{cacheLabel}</p>}
          {hits.meta.status && (
            <p className="text-sm text-slate-600">
              {hits.meta.status === 'ok'
                ? 'Resultados obtidos agora.'
                : hits.meta.status === 'parcial'
                  ? 'Alguns mecanismos falharam; mostrando o que veio dos que responderam.'
                  : hits.meta.status === 'indisponivel'
                    ? 'Nenhum mecanismo devolveu resultado agora (bloqueio, timeout ou erro de leitura). Tente a aba Web ou outra consulta.'
                    : `Status da busca: ${hits.meta.status}`}
            </p>
          )}
          {hits.meta.providers?.map((provider) => (
            <p key={provider.engine} className="text-sm">
              Provedor {provider.engine}: {provider.status}
              {provider.status !== 'ok' && provider.reason ? ` — ${provider.reason}` : ''}
            </p>
          ))}
          {tab === 'pesquisas' && (
            <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
              <p>Registro encontrado não significa que a notícia sobre a pesquisa esteja correta. Pesquisa não encontrada não significa fraude.</p>
              <p>O cadastro não contém resultados percentuais.</p>
            </div>
          )}
          {tab === 'checagens' && (
            <p className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
              Esta ferramenta não classifica alegações como verdadeiras ou falsas; ela ajuda a localizar evidências publicadas.
            </p>
          )}
          {tab === 'pesquisas' ? (
            <PollResults data={(hits as Envelope<RegisteredPoll[]>).data} />
          ) : (
            <HitResults data={(hits as Envelope<SearchHit[]>).data} tab={tab} metaStatus={hits.meta.status} />
          )}
          {Array.isArray(hits.data) && hits.data.length === 0 && (
            <EmptyBlock>Nenhum resultado retornado para esta consulta.</EmptyBlock>
          )}
        </div>
      )}
      <p className="text-xs text-slate-500">
        Atalhos externos (secundários):{' '}
        <a className="underline" href="https://www.google.com/search" rel="noopener noreferrer nofollow" target="_blank">Abrir no Google</a>
        {' · '}
        <a className="underline" href="https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas" rel="noopener noreferrer nofollow" target="_blank">Consulta PesqEle (TSE)</a>
        {' · '}
        <a className="underline" href="https://pesqele-divulgacao.tse.jus.br/" rel="noopener noreferrer nofollow" target="_blank">Sistema PesqEle</a>
      </p>
    </div>
  )
}

function HitResults({ data, tab, metaStatus }: { data: SearchHit[]; tab: Tab; metaStatus?: string }) {
  return (
    <ul className="space-y-3">
      {data.map((hit) => (
        <li key={hit.url} className="rounded-lg border border-slate-200 bg-white p-3">
          <a className="font-medium text-atlas-800 underline" href={hit.url} rel="noopener noreferrer nofollow" target="_blank">
            {hit.title}
          </a>
          <p className="text-xs text-slate-500">
            {hit.domain}
            {hit.engines?.length ? ` · ${hit.engines.join(', ')}` : ''}
            {' · '}
            <a className="underline" href={hit.url} rel="noopener noreferrer nofollow" target="_blank">
              Abrir matéria
            </a>
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{hit.snippet}</p>
          <p className="mt-1 text-xs text-slate-500">
            {hit.published_at ? formatDateTime(hit.published_at) : 'data não informada'}
          </p>
          {tab === 'checagens' && (
            <p className="mt-1 text-sm font-medium text-slate-800">{factCheckLabel(hit.status, metaStatus)}</p>
          )}
        </li>
      ))}
    </ul>
  )
}

function PollResults({ data }: { data: RegisteredPoll[] }) {
  return (
    <ul className="space-y-3">
      {data.map((poll) => (
        <li key={poll.nr_protocolo_registro} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <p className="font-medium">{poll.nm_empresa} {poll.nm_empresa_fantasia ? `(${poll.nm_empresa_fantasia})` : ''}</p>
          <p>Protocolo {poll.nr_protocolo_registro} · {poll.ds_cargo} · {poll.sg_uf} {poll.nm_ue}</p>
          <p>Registro: {formatDateTime(poll.dt_registro, 'data não informada')} · Divulgação: {formatDateTime(poll.dt_divulgacao, 'data não informada')}</p>
          <p>Entrevistados: {poll.qt_entrevistado ?? '—'} · Status: {poll.status}</p>
          {poll.pesqele_url && (
            <a className="text-atlas-700 underline" href={poll.pesqele_url} rel="noopener noreferrer nofollow" target="_blank">
              Consultar protocolo {poll.nr_protocolo_registro} no PesqEle
            </a>
          )}
        </li>
      ))}
    </ul>
  )
}

export default function SearchPage() {
  return <SearchPageInner />
}

export function SearchPollsRedirect() {
  return <Navigate to="/pesquisa?aba=pesquisas" replace />
}
