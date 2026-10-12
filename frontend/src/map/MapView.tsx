import { useMemo, useState } from 'react'
import type { CandidateMunicipality, GeometryProperties, LeaderMunicipality, SequentialLegend } from '../api/types'
import { Button } from '../components/Ui'
import { TIE_COLOR } from '../lib/mapColors'
import MapLibreView, { webglAvailable } from './MapLibreView'
import { isLeaderRow, paintCollection } from './paintCollection'
import SvgChoropleth from './SvgChoropleth'

type Props = {
  geometry: GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties>
  rows: Array<LeaderMunicipality | CandidateMunicipality>
  mode: 'leader' | 'candidate' | 'margin'
  bands?: SequentialLegend['bands']
  candidateColor?: string
  onSelectMunicipio?: (tse: string, uf: string, ibge?: string) => void
  onSelectUf?: (uf: string) => void
  flyToIbge?: string | null
  selectedId?: string | null
}

export default function MapView({ geometry, rows, mode, bands, candidateColor, onSelectMunicipio, onSelectUf, flyToIbge, selectedId }: Props) {
  const [engine, setEngine] = useState<'2d' | '3d'>(webglAvailable() ? '3d' : '2d')
  const [glFailed, setGlFailed] = useState(false)

  const painted = useMemo(
    () => paintCollection(geometry, rows, mode, bands, candidateColor),
    [geometry, rows, mode, bands, candidateColor],
  )

  const legend = useMemo(() => {
    const counts = new Map<string, { label: string; color: string; n: number }>()
    for (const row of rows) {
      if (!isLeaderRow(row) || !row.leader || row.is_exterior || row.tie) continue
      const key = String(row.leader.option_id)
      const cur = counts.get(key) ?? { label: row.leader.label, color: row.leader.color || TIE_COLOR, n: 0 }
      cur.n += 1
      counts.set(key, cur)
    }
    return [...counts.values()].sort((a, b) => b.n - a.n).slice(0, 8)
  }, [rows])

  const gl = webglAvailable()
  const view = engine === '3d' && gl && !glFailed ? '3d' : 'svg'

  return (
    <div className="space-y-2">
      {legend.length > 0 && (
        <ul className="flex flex-wrap gap-3 text-xs text-slate-700">
          {legend.map((item) => (
            <li key={item.label} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-sm ring-1 ring-slate-300" style={{ background: item.color }} aria-hidden />
              {item.label}
            </li>
          ))}
          <li className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm ring-1 ring-slate-300" style={{ background: TIE_COLOR }} aria-hidden />
            Empate
          </li>
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant={engine === '2d' ? 'primary' : 'secondary'} onClick={() => setEngine('2d')}>
          Mapa 2D
        </Button>
        <Button
          variant={engine === '3d' ? 'primary' : 'secondary'}
          onClick={() => {
            setGlFailed(false)
            setEngine('3d')
          }}
          disabled={!gl}
        >
          Mapa 3D
        </Button>
      </div>
      {view === '3d' ? (
        <MapLibreView
          collection={painted}
          mode="3d"
          grain={
            painted.features[0]?.properties?.cd_municipio_ibge
              ? selectedId
                ? 'local'
                : 'municipio'
              : 'uf'
          }
          selectedId={selectedId}
          onFail={() => setGlFailed(true)}
          onSelectMunicipio={onSelectMunicipio}
          onSelectUf={onSelectUf}
          flyToId={flyToIbge}
        />
      ) : (
        <SvgChoropleth
          collection={painted}
          onSelectMunicipio={onSelectMunicipio}
          onSelectUf={onSelectUf}
          highlightId={selectedId || flyToIbge}
        />
      )}
      {engine === '3d' && glFailed && (
        <p className="text-xs text-amber-800">O mapa 3D não iniciou neste navegador. O 2D abaixo usa as mesmas cores de vencedor.</p>
      )}
      <p className="text-xs text-slate-600">
        {painted.features.length > 0
          ? painted.features[0]?.properties?.cd_municipio_ibge
            ? `${painted.features.length} municípios no mapa. Aproxime e clique para entrar no município.`
            : `${painted.features.length} estados no mapa. Clique num estado para ver os municípios com a cor de quem venceu.`
          : 'Ainda não há território para desenhar neste recorte.'}
        {' '}Cada território usa a cor da candidatura que teve mais votos válidos ali. Empate em cinza-escuro; sem dados em cinza-claro. O exterior não entra no mapa.
      </p>
    </div>
  )
}
