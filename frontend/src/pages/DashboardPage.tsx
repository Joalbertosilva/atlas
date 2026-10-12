import { lazy, Suspense, useState } from 'react'
import { useNavigate } from 'react-router'
import { csvUrl } from '../api/client'
import type { SequentialLegend } from '../api/types'
import { Wordmark } from '../components/Brand'
import { Filters } from '../components/Filters'
import { MunicipalityTable } from '../components/MunicipalityTable'
import { Ranking } from '../components/Ranking'
import { ResultBoard } from '../components/ResultBoard'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import { StateWinners } from '../components/StateWinners'
import { SummaryCards } from '../components/SummaryCards'
import { useGeometry, useMunicipalityResults, useOffices, useRanking, useSummary, useUfLeaders } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { scopeSearch } from '../lib/scopeLinks'
import { canFetchOverview, canFetchResults, needsUf, scopeQuery } from '../lib/scope'

const MapView = lazy(() => import('../map/MapView'))

export default function DashboardPage() {
  const { scope } = useScopeParams()
  const navigate = useNavigate()
  const [kind, setKind] = useState<'candidatura' | 'todas'>('candidatura')
  const [asTable, setAsTable] = useState(false)
  const overview = canFetchOverview(scope)
  const summary = useSummary(scope)
  const ranking = useRanking(scope, kind)
  const geomLevel = scope.uf ? 'municipio' : 'uf'
  const mapRows = useMunicipalityResults(scope, 'leader', undefined, geomLevel, !asTable && !overview)
  const mun = useMunicipalityResults(scope, 'leader', undefined, 'municipio', asTable || Boolean(scope.uf))
  const ufLeaders = useUfLeaders(scope, overview)
  const offices = useOffices()
  const geom = useGeometry(geomLevel, scope.uf || undefined, (canFetchResults({ ...scope, municipio: '' }) || overview) && !asTable)
  const ready = canFetchResults(scope)
  const cargoLabel = offices.data?.data.find((o) => o.cd_cargo === scope.cargo)?.ds_cargo ?? `Cargo ${scope.cargo}`
  const yearTitle = scope.ano === 2022 ? 'Eleição 2022' : 'Eleição 2026'

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white px-5 py-6 shadow-sm sm:px-7">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="min-w-0 max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-atlas-700">Atlas Eleitoral</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-atlas-900">{yearTitle}</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              Resultados oficiais do TSE por cargo e território. Situação de eleito ou segundo turno vem do TSE —
              não da posição na lista.
            </p>
          </div>
          <Wordmark size="hero" />
        </div>
      </section>
      <Filters />
      {overview && (
        <section className="min-w-0 space-y-4">
          <p className="text-sm text-slate-600">
            {cargoLabel} é disputa por UF. O mapa mostra quem teve mais votos válidos em cada estado.
            Clique no estado para abrir o ranking completo. Situação de eleito vem do TSE, não da cor do mapa.
          </p>
          {ufLeaders.isPending && <LoadingBlock label="Carregando mapa por UF…" />}
          {ufLeaders.isError && <ErrorBlock error={ufLeaders.error} />}
          {geom.isPending && <LoadingBlock label="Carregando geometria…" />}
          {ufLeaders.data && geom.data && (
            <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
              <MapView
                geometry={geom.data}
                rows={ufLeaders.data.data}
                mode="leader"
                onSelectUf={(uf) => navigate(`/${scopeSearch({ ...scope, uf })}`)}
              />
            </Suspense>
          )}
          {ufLeaders.data && ufLeaders.data.data.some((row) => row.leader) && (
            <StateWinners
              rows={ufLeaders.data.data}
              ano={scope.ano}
              onSelectUf={(uf) => navigate(`/${scopeSearch({ ...scope, uf })}`)}
            />
          )}
          {ufLeaders.data && !ufLeaders.data.data.some((row) => row.leader) && (
            <EmptyBlock>Este cargo ainda não está publicado para {scope.ano} nesta base.</EmptyBlock>
          )}
        </section>
      )}
      {!ready && needsUf(scope.cargo) && !overview && (
        <EmptyBlock>Para este cargo informe a UF: não existe disputa nacional.</EmptyBlock>
      )}
      {ready && summary.isPending && <LoadingBlock />}
      {ready && summary.isError && <ErrorBlock error={summary.error} />}
      {ready && summary.data && (
        <>
          <SourceMeta meta={summary.data.meta} />
          {ranking.data && (
            <ResultBoard
              summary={summary.data.data}
              ranking={ranking.data.data}
              cargoLabel={cargoLabel}
              ano={scope.ano}
            />
          )}
          <SummaryCards data={summary.data.data} cargo={scope.cargo} />
        </>
      )}
      {ready && (
        <div className="grid min-w-0 gap-5">
          <div className="min-w-0">
            {ranking.isPending && <LoadingBlock label="Carregando ranking…" />}
            {ranking.isError && <ErrorBlock error={ranking.error} />}
            {ranking.data && (
              <Ranking
                rows={ranking.data.data}
                cargo={scope.cargo}
                ano={scope.ano}
                meta={ranking.data.meta}
                kind={kind}
                onKindChange={setKind}
                csvHref={csvUrl('ranking', { ...scopeQuery(scope), kind })}
              />
            )}
          </div>
          <section className="min-w-0 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Mapa</h2>
              <button type="button" className="btn btn-ghost !min-h-8" onClick={() => setAsTable((v) => !v)}>
                {asTable ? 'Ver mapa' : 'Ver como tabela'}
              </button>
            </div>
            {(asTable ? mun.isPending : mapRows.isPending) && <LoadingBlock label="Carregando mapa…" />}
            {(asTable ? mun.isError : mapRows.isError) && <ErrorBlock error={(asTable ? mun.error : mapRows.error)} />}
            {mun.data && asTable && <MunicipalityTable rows={mun.data.data} mode="leader" />}
            {mapRows.data && !asTable && (
              geom.isPending ? <LoadingBlock label="Carregando geometria…" /> : geom.isError ? <ErrorBlock error={geom.error} /> : geom.data ? (
                <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
                  <MapView
                    geometry={geom.data}
                    rows={mapRows.data.data}
                    mode="leader"
                    bands={(mapRows.data.meta.legend as SequentialLegend | undefined)?.bands}
                    onSelectUf={(uf) => navigate(`/mapa${scopeSearch({ ...scope, uf })}`)}
                    onSelectMunicipio={(tse, uf) => navigate(`/explorar${scopeSearch({ ...scope, uf, municipio: tse })}`)}
                  />
                </Suspense>
              ) : (
                <EmptyBlock>Geometria ainda não publicada para este recorte.</EmptyBlock>
              )
            )}
          </section>
        </div>
      )}
    </div>
  )
}
