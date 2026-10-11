import { lazy, Suspense, useState } from 'react'
import { useNavigate } from 'react-router'
import { csvUrl } from '../api/client'
import type { SequentialLegend } from '../api/types'
import { Filters } from '../components/Filters'
import { MunicipalityTable } from '../components/MunicipalityTable'
import { Ranking } from '../components/Ranking'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import { SummaryCards } from '../components/SummaryCards'
import { useGeometry, useMunicipalityResults, useRanking, useSummary } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { canFetchResults, needsUf, scopeQuery } from '../lib/scope'

const MapView = lazy(() => import('../map/MapView'))

export default function DashboardPage() {
  const { scope } = useScopeParams()
  const navigate = useNavigate()
  const [kind, setKind] = useState<'candidatura' | 'todas'>('candidatura')
  const [asTable, setAsTable] = useState(false)
  const summary = useSummary(scope)
  const ranking = useRanking(scope, kind)
  const mun = useMunicipalityResults(scope, 'leader')
  const geomLevel = scope.uf ? 'municipio' : 'uf'
  const geom = useGeometry(geomLevel, scope.uf || undefined, canFetchResults({ ...scope, municipio: '' }) && !asTable)
  const ready = canFetchResults(scope)

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-slate-900">Resultados</h1>
      <Filters />
      {!ready && needsUf(scope.cargo) && (
        <EmptyBlock>Para este cargo informe a UF: não existe disputa nacional.</EmptyBlock>
      )}
      {ready && summary.isPending && <LoadingBlock />}
      {ready && summary.isError && <ErrorBlock error={summary.error} />}
      {ready && summary.data && (
        <>
          <SourceMeta meta={summary.data.meta} />
          <SummaryCards data={summary.data.data} cargo={scope.cargo} />
        </>
      )}
      {ready && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Mapa</h2>
              <button type="button" className="text-sm text-atlas-700 underline" onClick={() => setAsTable((v) => !v)}>
                {asTable ? 'Ver mapa' : 'Ver como tabela'}
              </button>
            </div>
            {mun.isPending && <LoadingBlock label="Carregando municípios…" />}
            {mun.isError && <ErrorBlock error={mun.error} />}
            {mun.data && asTable && <MunicipalityTable rows={mun.data.data} mode="leader" />}
            {mun.data && !asTable && (
              geom.isPending ? <LoadingBlock label="Carregando geometria…" /> : geom.isError ? <ErrorBlock error={geom.error} /> : geom.data ? (
                <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
                  <MapView
                    geometry={geom.data}
                    rows={mun.data.data}
                    mode="leader"
                    bands={(mun.data.meta.legend as SequentialLegend | undefined)?.bands}
                    onSelectUf={(uf) => navigate(`/mapa?uf=${uf}&cargo=${scope.cargo}&turno=${scope.turno}`)}
                  />
                </Suspense>
              ) : (
                <EmptyBlock>Geometria ainda não publicada para este recorte.</EmptyBlock>
              )
            )}
          </section>
          <div>
            {ranking.isPending && <LoadingBlock label="Carregando ranking…" />}
            {ranking.isError && <ErrorBlock error={ranking.error} />}
            {ranking.data && (
              <Ranking
                rows={ranking.data.data}
                cargo={scope.cargo}
                meta={ranking.data.meta}
                kind={kind}
                onKindChange={setKind}
                csvHref={csvUrl('ranking', { ...scopeQuery(scope), kind })}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
