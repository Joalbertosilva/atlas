import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { csvUrl } from '../api/client'
import type { LeaderLegend, LeaderMunicipality, SequentialLegend } from '../api/types'
import { Filters } from '../components/Filters'
import { MunicipalityTable } from '../components/MunicipalityTable'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { ResultBoard } from '../components/ResultBoard'
import { SourceMeta } from '../components/SourceMeta'
import { StateWinners } from '../components/StateWinners'
import {
  useGeometry,
  useMunicipalityResults,
  useOffices,
  useRanking,
  useStates,
  useSummary,
  useUfLeaders,
} from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { canFetchOverview, canFetchResults, needsUf } from '../lib/scope'
import { scopeSearch } from '../lib/scopeLinks'
import { MAP_NO_DATA, TIE_COLOR, leaderLegendItems, sequentialLegendItems } from '../lib/mapColors'

const MapView = lazy(() => import('../map/MapView'))

export default function MapPage() {
  const { scope, update } = useScopeParams()
  const [asTable, setAsTable] = useState(false)
  const [search, setSearch] = useState('')
  const [flyTo, setFlyTo] = useState<string | null>(null)
  const mode = scope.modo === 'candidate' ? 'candidate' : 'leader'
  const overview = canFetchOverview(scope)
  const results = useMunicipalityResults({ ...scope, municipio: '' }, mode, scope.option, scope.uf ? 'municipio' : 'uf')
  const ranking = useRanking({ ...scope, municipio: '' }, 'candidatura', 1, 80)
  const localSummary = useSummary(scope)
  const localRanking = useRanking(scope, 'candidatura', 1, 12)
  const offices = useOffices()
  const states = useStates()
  const ufLeaders = useUfLeaders(scope, overview)
  const geom = useGeometry(
    scope.uf ? 'municipio' : 'uf',
    scope.uf || undefined,
    canFetchResults({ ...scope, municipio: '' }) || overview,
  )
  const ready = canFetchResults({ ...scope, municipio: '' })
  const cargoLabel = offices.data?.data.find((item) => item.cd_cargo === scope.cargo)?.ds_cargo ?? 'Cargo'
  const ufName = states.data?.data.find((item) => item.sg_uf === scope.uf)?.nm_uf ?? scope.uf
  const selectedMun = scope.municipio
    ? (results.data?.data ?? []).find((row) => row.cd_municipio_tse === scope.municipio)
    : undefined

  function goBrasil() {
    setSearch('')
    setFlyTo(null)
    update({ uf: '', municipio: '' })
  }

  function goUf(uf: string) {
    setSearch('')
    setFlyTo(null)
    update({ uf, municipio: '' })
  }

  function goMunicipio(tse: string, uf: string, ibge?: string) {
    setFlyTo(ibge || tse)
    update({ uf, municipio: tse })
  }

  const legendItems = useMemo(() => {
    if (!results.data) return []
    const raw =
      scope.modo === 'candidate'
        ? sequentialLegendItems(results.data.meta.legend as SequentialLegend | undefined)
        : leaderLegendItems(results.data.meta.legend as LeaderLegend | undefined, results.data.data as LeaderMunicipality[])
    return raw.map((item) => {
      const lower = item.label.toLowerCase()
      if (lower === 'empate') return { ...item, color: TIE_COLOR }
      if (lower.includes('sem dados')) return { ...item, color: MAP_NO_DATA }
      return item
    })
  }, [results.data, scope.modo])

  const rows = results.data?.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">Mapa</h1>
        <button type="button" className="btn btn-secondary" onClick={() => setAsTable((v) => !v)}>
          {asTable ? 'Ver mapa' : 'Ver como tabela'}
        </button>
      </div>
      <Filters showMode />
      <nav aria-label="Recorte do mapa">
        <ol className="flex flex-wrap items-center gap-1 text-sm text-slate-600">
          <li>
            <button type="button" className="text-atlas-800 underline" onClick={goBrasil}>
              Brasil
            </button>
          </li>
          {/^[A-Z]{2}$/.test(scope.uf) && (
            <li>
              <span aria-hidden className="px-1 text-slate-400">
                /
              </span>
              <button type="button" className="text-atlas-800 underline" onClick={() => goUf(scope.uf)}>
                {ufName}
              </button>
            </li>
          )}
          {selectedMun && (
            <li>
              <span aria-hidden className="px-1 text-slate-400">
                /
              </span>
              <span className="font-medium text-slate-900">{selectedMun.nm_municipio}</span>
            </li>
          )}
        </ol>
      </nav>
      <p className="text-sm text-slate-600">
        {scope.municipio
          ? 'Município aberto no mapa. A cor de cada vizinho continua sendo de quem venceu ali. Volte ao estado para escolher outro.'
          : scope.uf
            ? 'Municípios do estado, cada um na cor de quem teve mais votos válidos. Clique para entrar no município.'
            : 'Clique num estado para ver a divisão municipal de quem ganhou e quem ficou em segundo.'}
      </p>
      {scope.modo === 'candidate' && (
        <label className="block max-w-lg text-sm">
          <span className="mb-1 block font-medium">Candidatura</span>
          <select
            className="field"
            value={scope.option}
            onChange={(event) => update({ option: event.target.value })}
          >
            <option value="">Selecione uma candidatura</option>
            {(ranking.data?.data ?? []).map((row) => (
              <option key={row.option_id} value={String(row.option_id)}>
                {row.nr_votavel} — {row.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {overview && (
        <div className="min-w-0 space-y-4">
          <p className="text-sm text-slate-600">
            Este cargo é por UF. Clique no estado para ver os municípios. Situação de eleito vem do TSE.
          </p>
          {ufLeaders.isPending && <LoadingBlock />}
          {ufLeaders.isError && <ErrorBlock error={ufLeaders.error} />}
          {ufLeaders.data && geom.data && (
            <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
              <MapView
                geometry={geom.data}
                rows={ufLeaders.data.data}
                mode="leader"
                onSelectUf={goUf}
              />
            </Suspense>
          )}
          {ufLeaders.data && ufLeaders.data.data.some((row) => row.leader) && (
            <StateWinners rows={ufLeaders.data.data} ano={scope.ano} onSelectUf={goUf} />
          )}
          {ufLeaders.data && !ufLeaders.data.data.some((row) => row.leader) && (
            <EmptyBlock>Este cargo ainda não está publicado para {scope.ano} nesta base.</EmptyBlock>
          )}
        </div>
      )}
      {!ready && needsUf(scope.cargo) && !overview && <EmptyBlock>Para este cargo informe a UF.</EmptyBlock>}
      {ready && scope.modo === 'candidate' && !scope.option && (
        <EmptyBlock>Selecione uma candidatura para ver a intensidade por município.</EmptyBlock>
      )}
      {results.isError && <ErrorBlock error={results.error} />}
      {Boolean(scope.uf) && (
        <label className="block max-w-md text-sm">
          <span className="mb-1 block font-medium">Buscar município no mapa</span>
          <input
            className="field"
            value={search}
            onChange={(event) => {
              const value = event.target.value
              setSearch(value)
              const q = value.trim().toLowerCase()
              if (!q) {
                setFlyTo(null)
                return
              }
              const hits = rows.filter((row) => row.nm_municipio.toLowerCase().includes(q) && row.cd_municipio_ibge)
              const exact = hits.find((row) => row.nm_municipio.toLowerCase() === q)
              setFlyTo((exact ?? hits[0])?.cd_municipio_ibge ?? null)
            }}
            onKeyDown={(event) => {
              if (event.key !== 'Enter') return
              event.preventDefault()
              const q = search.trim().toLowerCase()
              const hits = rows.filter((row) => row.nm_municipio.toLowerCase().includes(q) && row.cd_municipio_tse)
              const exact = hits.find((row) => row.nm_municipio.toLowerCase() === q)
              const hit = exact ?? hits[0]
              if (hit?.cd_municipio_tse) goMunicipio(hit.cd_municipio_tse, hit.sg_uf, hit.cd_municipio_ibge ?? undefined)
            }}
            placeholder="Nome do município — Enter para entrar"
          />
        </label>
      )}
      {ready && results.isPending && <LoadingBlock />}
      {ready && results.data && asTable && (
        <MunicipalityTable
          rows={rows}
          mode={scope.modo}
          candidateColor={(results.data.meta.legend as SequentialLegend | undefined)?.color || undefined}
        />
      )}
      {ready && results.data && !asTable && geom.data && (
        <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
          <MapView
            geometry={geom.data}
            rows={rows}
            mode={scope.modo}
            bands={(results.data.meta.legend as SequentialLegend | undefined)?.bands}
            candidateColor={(results.data.meta.legend as SequentialLegend | undefined)?.color || undefined}
            flyToIbge={flyTo}
            selectedId={selectedMun?.cd_municipio_ibge || scope.municipio || null}
            onSelectMunicipio={goMunicipio}
            onSelectUf={goUf}
          />
        </Suspense>
      )}
      {geom.isError && <ErrorBlock error={geom.error} />}
      {scope.municipio && localSummary.isPending && <LoadingBlock label="Abrindo o município…" />}
      {scope.municipio && localSummary.isError && <ErrorBlock error={localSummary.error} />}
      {scope.municipio && localSummary.data && localRanking.data && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-base font-semibold text-slate-900">
              {selectedMun?.nm_municipio ?? 'Município'} ({scope.uf})
            </h2>
            <Link className="text-sm text-atlas-700 underline" to={`/explorar${scopeSearch(scope)}`}>
              Ver seções e locais deste município
            </Link>
          </div>
          <ResultBoard
            summary={localSummary.data.data}
            ranking={localRanking.data.data}
            cargoLabel={cargoLabel}
            ano={scope.ano}
          />
        </section>
      )}
      {results.data && <SourceMeta meta={results.data.meta} />}
      {ready && results.data && (
        <div className="flex flex-wrap gap-3 text-xs">
          {legendItems.map((item) => (
            <span key={item.label} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 ring-1 ring-slate-300" style={{ background: item.color }} aria-hidden />
              {item.label}
              {item.municipios !== undefined ? ` (${item.municipios})` : ''}
            </span>
          ))}
          {scope.modo === 'margin' && (
            <span className="text-slate-500">Diferença em pontos percentuais dos votos válidos do município (1º − 2º).</span>
          )}
        </div>
      )}
      {ready && results.data && (
        <a className="inline-block text-sm text-atlas-700 underline" href={csvUrl('municipalities', {
          cargo: scope.cargo,
          turno: scope.turno,
          uf: scope.uf || undefined,
          mode,
          level: scope.uf ? 'municipio' : 'uf',
          option_id: mode === 'candidate' ? scope.option : undefined,
        })}>
          Exportar CSV dos municípios
        </a>
      )}
      <p className="text-xs text-slate-500">Empate em cinza-escuro; territórios sem dado em cinza-claro.</p>
    </div>
  )
}
