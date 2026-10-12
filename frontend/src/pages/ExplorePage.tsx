import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Filters } from '../components/Filters'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import {
  usePollingPlaces,
  useSectionResults,
  useSections,
  useStates,
  useMunicipalities,
  useZones,
} from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { formatInt, formatPctShort, kindLabel } from '../lib/format'

function unidentified(linkStatus?: string | null, placeName?: string | null) {
  return !placeName || (linkStatus && linkStatus !== 'confirmado')
}

export default function ExplorePage() {
  const { scope, update } = useScopeParams()
  const [params, setParams] = useSearchParams()
  const zona = params.get('zona') || ''
  const local = params.get('local') || ''
  const secao = params.get('secao') || ''
  const states = useStates()
  const municipalities = useMunicipalities(scope.uf || undefined, undefined, Boolean(scope.uf && !scope.municipio))
  const zones = useZones(scope.municipio, scope.cargo, scope.turno)
  const places = usePollingPlaces(scope.municipio, zona || undefined)
  const sections = useSections(scope.municipio, zona || undefined, local || undefined)
  const sectionResults = useSectionResults(secao, scope.cargo, scope.turno)

  const crumbs = useMemo(() => {
    const items = [{ label: 'Brasil', href: '/explorar' }]
    if (scope.uf) items.push({ label: scope.uf, href: `/explorar?uf=${scope.uf}&cargo=${scope.cargo}&turno=${scope.turno}` })
    if (scope.municipio) {
      items.push({
        label: `Município ${scope.municipio}`,
        href: `/explorar?uf=${scope.uf}&municipio=${scope.municipio}&cargo=${scope.cargo}&turno=${scope.turno}`,
      })
    }
    if (zona) items.push({ label: `Zona ${zona}`, href: `${items[items.length - 1].href}&zona=${zona}` })
    if (local) items.push({ label: `Local ${local}`, href: `${items[items.length - 1].href}&local=${local}` })
    if (secao) items.push({ label: `Seção ${secao}`, href: `${items[items.length - 1].href}&secao=${secao}` })
    return items
  }, [scope, zona, local, secao])

  function setExtra(patch: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(patch)) {
      if (!value) next.delete(key)
      else next.set(key, value)
    }
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Explorar território</h1>
      <Filters />
      <nav aria-label="Trilha" className="flex flex-wrap gap-2 text-sm text-slate-600">
        {crumbs.map((crumb, i) => (
          <span key={crumb.href}>
            {i > 0 && ' / '}
            <Link className="text-atlas-700 underline" to={crumb.href}>{crumb.label}</Link>
          </span>
        ))}
      </nav>

      {!scope.uf && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Unidades da federação</h2>
          {states.isPending && <LoadingBlock />}
          {states.isError && <ErrorBlock error={states.error} />}
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(states.data?.data ?? []).map((state) => (
              <li key={state.sg_uf}>
                <button
                  type="button"
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-sm hover:bg-atlas-50"
                  onClick={() => update({ uf: state.sg_uf, municipio: '' })}
                >
                  {state.nm_uf} ({state.sg_uf})
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {scope.uf && !scope.municipio && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Municípios de {scope.uf}</h2>
          {municipalities.isPending && <LoadingBlock />}
          {municipalities.isError && <ErrorBlock error={municipalities.error} />}
          <ul className="max-h-[28rem] overflow-auto divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
            {(municipalities.data?.data ?? []).map((mun) => (
              <li key={mun.cd_municipio_tse}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-atlas-50"
                  onClick={() => update({ municipio: mun.cd_municipio_tse, uf: mun.sg_uf })}
                >
                  {mun.nm_municipio} · TSE {mun.cd_municipio_tse}
                  {mun.is_exterior ? ' · exterior' : ''}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {scope.municipio && !zona && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Zonas do município {scope.municipio}</h2>
          {zones.isPending && <LoadingBlock />}
          {zones.isError && <ErrorBlock error={zones.error} />}
          {zones.data && <SourceMeta meta={zones.data.meta} />}
          <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-2 py-2">Zona</th>
                  <th className="px-2 py-2">Aptos</th>
                  <th className="px-2 py-2">Comparecimento</th>
                  <th className="px-2 py-2">Válidos</th>
                  <th className="px-2 py-2">Líder</th>
                  <th className="px-2 py-2">Seções com voto</th>
                </tr>
              </thead>
              <tbody>
                {(zones.data?.data ?? []).map((zone) => (
                  <tr key={zone.nr_zona} className="border-t border-slate-100">
                    <td className="px-2 py-1.5">
                      <button type="button" className="text-atlas-700 underline" onClick={() => setExtra({ zona: zone.nr_zona, local: '', secao: '' })}>
                        {zone.nr_zona}
                      </button>
                    </td>
                    <td className="px-2 py-1.5">{formatInt(zone.qt_aptos)}</td>
                    <td className="px-2 py-1.5">{formatInt(zone.qt_comparecimento)}</td>
                    <td className="px-2 py-1.5">{formatInt(zone.qt_total_votos_validos)}</td>
                    <td className="px-2 py-1.5">
                      {zone.tie ? 'Empate' : zone.leader ? `${zone.leader.label} (${formatPctShort(zone.leader.pct_validos)})` : 'Sem dados'}
                    </td>
                    <td className="px-2 py-1.5">{formatInt(zone.sections_loaded)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {scope.municipio && zona && !secao && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Locais da zona {zona}</h2>
          {places.isPending && <LoadingBlock />}
          {places.isError && <ErrorBlock error={places.error} />}
          {places.data && <SourceMeta meta={places.data.meta} />}
          <ul className="space-y-2">
            {(places.data?.data ?? []).map((place) => (
              <li key={place.polling_place_id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
                <button type="button" className="font-medium text-atlas-700 underline" onClick={() => setExtra({ local: String(place.polling_place_id) })}>
                  {place.nm_local_votacao}
                </button>
                <p className="text-slate-600">Tipo do local: {place.ds_tipo_local || 'não informado'} — nem todo local é escola.</p>
                <p className="text-slate-600">{place.ds_endereco} {place.nm_bairro}</p>
                {place.coord_status === 'valida' && place.latitude != null && place.longitude != null ? (
                  <p className="text-xs text-slate-500">Coordenadas: {place.latitude}, {place.longitude}</p>
                ) : (
                  <p className="text-xs text-slate-500">Coordenadas não disponíveis (coord_status ≠ valida).</p>
                )}
              </li>
            ))}
          </ul>
          <div>
            <h3 className="mb-2 text-sm font-semibold">Seções (município → zona → seção)</h3>
            {sections.isPending && <LoadingBlock />}
            {sections.isError && <ErrorBlock error={sections.error} />}
            <ul className="divide-y divide-slate-100 rounded-md border border-slate-200 bg-white text-sm">
              {(sections.data?.data ?? []).map((section) => (
                <li key={section.section_id} className="px-3 py-2">
                  <button type="button" className="text-atlas-700 underline" onClick={() => setExtra({ secao: String(section.section_id) })}>
                    Seção {section.nr_secao}
                  </button>
                  {unidentified(section.link_status, section.nm_local_votacao) && (
                    <p className="text-amber-800">Local não identificado na base</p>
                  )}
                  {section.nm_local_votacao && <p className="text-slate-600">{section.nm_local_votacao}</p>}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {secao && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Resultado da seção {secao}</h2>
          {sectionResults.isPending && <LoadingBlock />}
          {sectionResults.isError && <ErrorBlock error={sectionResults.error} />}
          {sectionResults.data && (
            <>
              <SourceMeta meta={sectionResults.data.meta} />
              {unidentified(sectionResults.data.data.section.link_status, sectionResults.data.data.section.nm_local_votacao) && (
                <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                  Local não identificado na base
                </p>
              )}
              {sectionResults.data.data.section.ds_tipo_local && (
                <p className="text-sm text-slate-600">Tipo do local: {sectionResults.data.data.section.ds_tipo_local}</p>
              )}
              {sectionResults.data.data.turnout ? (
                <p className="text-sm text-slate-700">
                  Aptos {formatInt(sectionResults.data.data.turnout.qt_aptos)} · comparecimento {formatInt(sectionResults.data.data.turnout.qt_comparecimento)} ·
                  brancos {formatInt(sectionResults.data.data.turnout.qt_votos_brancos)} · nulos {formatInt(sectionResults.data.data.turnout.qt_votos_nulos)}
                </p>
              ) : (
                <EmptyBlock>Sem comparecimento de seção publicado para este cargo/turno.</EmptyBlock>
              )}
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Opção</th>
                    <th className="px-2 py-2">Tipo</th>
                    <th className="px-2 py-2">Votos digitados</th>
                  </tr>
                </thead>
                <tbody>
                  {sectionResults.data.data.results.map((row) => (
                    <tr key={row.option_id} className={row.kind !== 'candidatura' ? 'italic text-slate-600' : ''}>
                      <td className="px-2 py-1.5">{row.label}</td>
                      <td className="px-2 py-1.5">{kindLabel(row.kind)}</td>
                      <td className="px-2 py-1.5">{formatInt(row.qt_votos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      )}
    </div>
  )
}
