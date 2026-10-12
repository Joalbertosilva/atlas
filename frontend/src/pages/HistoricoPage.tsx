import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { GeometryProperties, PartyPlaceRow } from '../api/types'
import { Filters } from '../components/Filters'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import { useGeometry, usePartyCompare } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { formatInt, formatPctShort, formatSigned } from '../lib/format'
import { scopeSearch } from '../lib/scopeLinks'
import { canFetchResults, needsUf } from '../lib/scope'
import { NO_DATA_COLOR, sequentialFill, softenHex } from '../lib/mapColors'
import { partyColor } from '../lib/partyColors'
import SvgChoropleth from '../map/SvgChoropleth'

function parseGeometry(raw: unknown): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  try {
    const geometry = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!geometry || typeof geometry !== 'object' || !('type' in geometry)) return null
    const g = geometry as GeoJSON.Geometry
    if (g.type === 'Polygon' || g.type === 'MultiPolygon') return g
  } catch {
    return null
  }
  return null
}

export default function PartyComparePanel({ embedded = false }: { embedded?: boolean }) {
  const { scope, update } = useScopeParams()
  const [metrica, setMetrica] = useState<'nominais' | 'legenda' | 'ambos'>('nominais')
  const compare = usePartyCompare(scope, metrica, scope.option || undefined)
  const geomLevel = scope.uf ? 'municipio' : 'uf'
  const geom = useGeometry(geomLevel, scope.uf || undefined, canFetchResults({ ...scope, municipio: '' }))
  const ready = canFetchResults(scope)
  const data = compare.data?.data
  const selected = data?.nr_partido ?? ''
  const y22 = data?.years['2022']
  const y26 = data?.years['2026']

  const chart = useMemo(
    () =>
      (data?.parties ?? []).slice(0, 12).map((row) => ({
        name: `${row.sg_partido_2026 || row.sg_partido_2022 || row.nr_partido} (${row.nr_partido})`,
        v2022: row.votos_2022,
        v2026: row.votos_2026,
        color: partyColor(row.sg_partido_2026 || row.sg_partido_2022, row.nr_partido),
      })),
    [data],
  )

  const painted = useMemo(() => {
    if (!geom.data || !data) return null
    const byKey = new Map<string, PartyPlaceRow>()
    for (const place of data.places) {
      if (place.cd_municipio_ibge) byKey.set(String(place.cd_municipio_ibge), place)
      byKey.set(place.sg_uf, place)
    }
    const features = geom.data.features.flatMap((feature) => {
      const shape = parseGeometry(feature.geometry)
      if (!shape) return []
      const ibge = feature.properties?.cd_municipio_ibge ? String(feature.properties.cd_municipio_ibge) : ''
      const uf = feature.properties?.sg_uf ? String(feature.properties.sg_uf) : ''
      const place = (ibge && byKey.get(ibge)) || (uf ? byKey.get(uf) : undefined)
      const selectedParty = data.parties.find((row) => row.nr_partido === selected)
      const fill = placeFill(
        place,
        Boolean(y22?.available),
        partyColor(selectedParty?.sg_partido_2026 || selectedParty?.sg_partido_2022, selected || selectedParty?.nr_partido),
      )
      const tip = place
        ? `${place.nome} (${place.sg_uf}) — 2026 ${place.pct_2026 == null ? '—' : `${place.pct_2026.toFixed(2)}%`}${place.delta_pp == null ? '' : `; Δ ${place.delta_pp.toFixed(2)} pp`}${place.status === 'ausente' ? ' — sem dado comparável' : ''}`
        : `${feature.properties?.nm_municipio || feature.properties?.sg_uf || ''} — sem dados`
      const props: GeometryProperties & { fill: string; tooltip?: string } = { ...feature.properties, fill, tooltip: tip }
      return [{ type: 'Feature' as const, id: ibge || uf, geometry: shape, properties: props }]
    })
    return { type: 'FeatureCollection' as const, features }
  }, [geom.data, data, y22?.available])

  const topChange = useMemo(() => {
    return [...(data?.places ?? [])]
      .filter((p) => p.delta_pp != null)
      .sort((a, b) => Math.abs(b.delta_pp ?? 0) - Math.abs(a.delta_pp ?? 0))
      .slice(0, 5)
  }, [data])

  return (
    <div className="space-y-5">
      {!embedded && (
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Comparativo partidário 2022 × 2026</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Mesmo cargo, turno e território. Participação é o voto do partido sobre os válidos daquele recorte. Ponto
            percentual não é a mesma coisa que variação relativa. Sem dado de 2022 o campo fica vazio — não entra zero.
          </p>
        </div>
      )}
      {embedded && (
        <p className="text-sm text-slate-600">
          Mesmo cargo, turno e território. Participação é o voto do partido sobre os válidos daquele recorte. Sem dado
          de 2022 o campo fica vazio — não entra zero.
        </p>
      )}
      {!embedded && <Filters />}
      <fieldset className="flex flex-wrap gap-4 text-sm">
        <legend className="sr-only">Métrica do partido</legend>
        {(['nominais', 'legenda', 'ambos'] as const).map((item) => (
          <label key={item} className="inline-flex items-center gap-1.5">
            <input type="radio" name="metrica" checked={metrica === item} onChange={() => setMetrica(item)} />
            {item === 'nominais' ? 'Só nominais' : item === 'legenda' ? 'Só legenda' : 'Nominais + legenda'}
          </label>
        ))}
      </fieldset>
      {!ready && needsUf(scope.cargo) && <EmptyBlock>Para este cargo informe a UF.</EmptyBlock>}
      {compare.isPending && <LoadingBlock label="Comparando partidos…" />}
      {compare.isError && <ErrorBlock error={compare.error} />}
      {data && (
        <>
          <SourceMeta meta={compare.data?.meta} />
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            {y22?.available
              ? `2022 disponível (${formatInt(y22.total_validos)} válidos).`
              : '2022 ainda não foi importado nesta base. Os números de 2026 abaixo são reais; a diferença entre anos fica indisponível.'}{' '}
            2026: {y26?.available ? `${formatInt(y26.total_validos)} válidos.` : 'indisponível.'}
          </p>
          {data.parties.length > 0 && (
            <label className="block max-w-md text-sm">
              <span className="mb-1 block font-medium">Partido no mapa e no resumo</span>
              <select
                className="w-full rounded-md border border-slate-300 bg-white px-2 py-2"
                value={selected}
                onChange={(event) => update({ option: event.target.value })}
              >
                {data.parties.map((row) => (
                  <option key={row.nr_partido} value={row.nr_partido}>
                    {row.nr_partido} · {row.sg_partido_2026 || row.sg_partido_2022 || 'sem sigla'}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="h-72 min-w-0 overflow-x-auto rounded-lg border border-slate-200 bg-white p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={70} />
                <YAxis />
                <Tooltip formatter={(value) => (value == null ? '—' : formatInt(Number(value)))} />
                <Bar dataKey="v2022" name="2022">
                  {chart.map((row) => (
                    <Cell key={`22-${row.name}`} fill={softenHex(row.color, 0.45)} />
                  ))}
                </Bar>
                <Bar dataKey="v2026" name="2026">
                  {chart.map((row) => (
                    <Cell key={`26-${row.name}`} fill={row.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">Comparativo partidário 2022 e 2026</caption>
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-2 py-2">Nº</th>
                  <th className="px-2 py-2">Sigla 2022</th>
                  <th className="px-2 py-2">Sigla 2026</th>
                  <th className="px-2 py-2">Votos 2022</th>
                  <th className="px-2 py-2">Votos 2026</th>
                  <th className="px-2 py-2">% 2022</th>
                  <th className="px-2 py-2">% 2026</th>
                  <th className="px-2 py-2">Δ votos</th>
                  <th className="px-2 py-2">Δ pp</th>
                  <th className="px-2 py-2">Var. relativa</th>
                </tr>
              </thead>
              <tbody>
                {data.parties.map((row) => (
                  <tr key={row.nr_partido} className="border-t border-slate-100">
                    <td className="px-2 py-1.5 tabular-nums">{row.nr_partido}</td>
                    <td className="px-2 py-1.5">{row.sg_partido_2022 ?? '—'}</td>
                    <td className="px-2 py-1.5">{row.sg_partido_2026 ?? '—'}</td>
                    <td className="px-2 py-1.5 tabular-nums">{formatInt(row.votos_2022)}</td>
                    <td className="px-2 py-1.5 tabular-nums">{formatInt(row.votos_2026)}</td>
                    <td className="px-2 py-1.5 tabular-nums">{formatPctShort(row.pct_2022)}</td>
                    <td className="px-2 py-1.5 tabular-nums">{formatPctShort(row.pct_2026)}</td>
                    <td className="px-2 py-1.5 tabular-nums">{formatSigned(row.delta_votos)}</td>
                    <td className="px-2 py-1.5 tabular-nums">{formatSigned(row.delta_pp, 'pp')}</td>
                    <td className="px-2 py-1.5 tabular-nums">
                      {row.variacao_relativa === 'indisponivel' ? 'não calculável' : formatSigned(row.delta_rel_pct, 'pct')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <section className="space-y-3">
            <h2 className="text-base font-semibold">Onde mudou — partido {selected || '—'}</h2>
            {y22?.available && topChange.length > 0 ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {topChange.map((place) => (
                  <li key={place.place_id}>
                    {place.nome} ({place.sg_uf}): {formatSigned(place.delta_pp, 'pp')} na participação.
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-600">
                Sem 2022 importado não há variação territorial. O mapa abaixo mostra a participação de 2026 do partido
                selecionado.
              </p>
            )}
            {geom.isPending && <LoadingBlock label="Carregando malha…" />}
            {painted && (
              <SvgChoropleth
                collection={painted}
                onSelectUf={(uf) => update({ uf, municipio: '' })}
                onSelectMunicipio={(tse, uf) => update({ uf, municipio: tse })}
              />
            )}
          </section>
          <p className="text-sm">
            <Link className="text-atlas-700 underline" to={`/pesquisa${scopeSearch(scope)}`}>
              Buscar notícias deste recorte
            </Link>
            {' · '}
            <Link className="text-atlas-700 underline" to={`/evolucao${scopeSearch(scope)}`}>
              Ver pesquisas registradas
            </Link>
          </p>
        </>
      )}
    </div>
  )
}

function placeFill(place: PartyPlaceRow | undefined, has2022: boolean, partyHex: string): string {
  if (!place) return NO_DATA_COLOR
  const value = has2022 ? place.delta_pp : place.pct_2026
  if (value == null) return NO_DATA_COLOR
  if (has2022) {
    if (value > 1) return '#14532d'
    if (value > 0) return '#86efac'
    if (value < -1) return '#7f1d1d'
    if (value < 0) return '#fca5a5'
    return '#e2e8f0'
  }
  return sequentialFill(
    value,
    [{ min: 0, max: 10 }, { min: 10, max: 20 }, { min: 20, max: 30 }, { min: 30, max: 40 }, { min: 40, max: 100 }],
    partyHex,
  )
}
