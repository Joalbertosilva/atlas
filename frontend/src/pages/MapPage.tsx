import { lazy, Suspense, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { csvUrl } from '../api/client'
import type { LeaderLegend, LeaderMunicipality, SequentialLegend } from '../api/types'
import { Filters } from '../components/Filters'
import { MunicipalityTable } from '../components/MunicipalityTable'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import { useGeometry, useMunicipalityResults, useRanking } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { canFetchResults, needsUf } from '../lib/scope'
import { TIE_COLOR, NO_DATA_COLOR, leaderLegendItems, sequentialLegendItems } from '../lib/mapColors'

const MapView = lazy(() => import('../map/MapView'))

export default function MapPage() {
  const { scope, update } = useScopeParams()
  const navigate = useNavigate()
  const [asTable, setAsTable] = useState(false)
  const [search, setSearch] = useState('')
  const [flyTo, setFlyTo] = useState<string | null>(null)
  const mode = scope.modo === 'candidate' ? 'candidate' : 'leader'
  const results = useMunicipalityResults(scope, mode, scope.option)
  const ranking = useRanking({ ...scope, municipio: '' }, 'candidatura', 1, 80)
  const geom = useGeometry(scope.uf ? 'municipio' : 'uf', scope.uf || undefined, canFetchResults({ ...scope, municipio: '' }))
  const ready = canFetchResults({ ...scope, municipio: '' })

  const legendItems = useMemo(() => {
    if (!results.data) return []
    if (scope.modo === 'candidate') {
      const legend = results.data.meta.legend as SequentialLegend | undefined
      return sequentialLegendItems(legend)
    }
    const legend = results.data.meta.legend as LeaderLegend | undefined
    return leaderLegendItems(legend, results.data.data as LeaderMunicipality[])
  }, [results.data, scope.modo])

  const rows = results.data?.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">Mapa</h1>
        <button type="button" className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm" onClick={() => setAsTable((v) => !v)}>
          {asTable ? 'Ver mapa' : 'Ver como tabela'}
        </button>
      </div>
      <Filters showMode />
      {scope.modo === 'candidate' && (
        <label className="block max-w-lg text-sm">
          <span className="mb-1 block font-medium">Candidatura (option)</span>
          <select
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-2"
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
      {!ready && needsUf(scope.cargo) && <EmptyBlock>Para este cargo informe a UF.</EmptyBlock>}
      {ready && scope.modo === 'candidate' && !scope.option && (
        <EmptyBlock>Selecione uma candidatura para ver a intensidade por município.</EmptyBlock>
      )}
      {results.isError && <ErrorBlock error={results.error} />}
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
      <label className="block max-w-md text-sm">
        <span className="mb-1 block font-medium">Buscar município no mapa</span>
        <input
          className="w-full rounded-md border border-slate-300 px-2 py-2"
          value={search}
          onChange={(event) => {
            const value = event.target.value
            setSearch(value)
            const hit = rows.find((row) => row.nm_municipio.toLowerCase().includes(value.toLowerCase()) && row.cd_municipio_ibge)
            setFlyTo(hit?.cd_municipio_ibge ?? null)
          }}
          placeholder="Nome do município"
        />
      </label>
      {results.isPending && <LoadingBlock />}
      {results.data && asTable && <MunicipalityTable rows={rows} mode={scope.modo} />}
      {results.data && !asTable && geom.data && (
        <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
          <MapView
            geometry={geom.data}
            rows={rows}
            mode={scope.modo}
            bands={(results.data.meta.legend as SequentialLegend | undefined)?.bands}
            flyToIbge={flyTo}
            onSelectMunicipio={(tse, uf) => navigate(`/explorar?uf=${uf}&municipio=${tse}&cargo=${scope.cargo}&turno=${scope.turno}`)}
            onSelectUf={(uf) => update({ uf })}
          />
        </Suspense>
      )}
      {geom.isError && <ErrorBlock error={geom.error} />}
      {results.data && (
        <a className="inline-block text-sm text-atlas-700 underline" href={csvUrl('municipalities', {
          cargo: scope.cargo,
          turno: scope.turno,
          uf: scope.uf || undefined,
          mode,
          option_id: mode === 'candidate' ? scope.option : undefined,
        })}>
          Exportar CSV dos municípios
        </a>
      )}
      <p className="text-xs text-slate-500">Cores de empate {TIE_COLOR} e sem dados {NO_DATA_COLOR}. Join pelo código IBGE.</p>
    </div>
  )
}
