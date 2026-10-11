import { useEffect, useState } from 'react'
import type { Office, State } from '../api/types'
import { useMunicipalities, useOffices, useStates } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { needsUf } from '../lib/scope'
import { ErrorBlock, Skeleton } from './QueryState'

export function Filters({ showMode = false }: { showMode?: boolean }) {
  const { scope, update } = useScopeParams()
  const offices = useOffices()
  const states = useStates()
  const [munQ, setMunQ] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(munQ.trim()), 300)
    return () => window.clearTimeout(id)
  }, [munQ])

  const municipalities = useMunicipalities(scope.uf || undefined, debounced.length >= 2 ? debounced : undefined, debounced.length >= 2)

  const officeList: Office[] = offices.data?.data ?? []
  const stateList: State[] = states.data?.data ?? []

  return (
    <form
      className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      onSubmit={(event) => event.preventDefault()}
    >
      {offices.isError && <div className="sm:col-span-2 lg:col-span-4"><ErrorBlock error={offices.error} /></div>}
      {states.isError && <div className="sm:col-span-2 lg:col-span-4"><ErrorBlock error={states.error} /></div>}

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-800">Cargo</span>
        {offices.isPending ? (
          <Skeleton className="h-10" />
        ) : (
          <select
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-2"
            value={scope.cargo}
            onChange={(event) =>
              update({
                cargo: event.target.value,
                municipio: '',
                option: '',
                uf: event.target.value === '8' ? 'DF' : scope.uf === 'ZZ' && event.target.value !== '1' ? '' : scope.uf,
              })
            }
          >
            {officeList.length === 0 ? (
              <option value={scope.cargo}>{scope.cargo}</option>
            ) : (
              officeList.map((office) => (
                <option key={office.cd_cargo} value={office.cd_cargo}>
                  {office.ds_cargo}
                </option>
              ))
            )}
          </select>
        )}
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-800">Turno</span>
        <select
          className="w-full rounded-md border border-slate-300 bg-white px-2 py-2"
          value={String(scope.turno)}
          onChange={(event) => update({ turno: Number(event.target.value) === 2 ? 2 : 1 })}
        >
          <option value="1">1º turno</option>
          <option value="2">2º turno</option>
        </select>
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-800">UF{needsUf(scope.cargo) ? ' (obrigatória)' : ''}</span>
        {states.isPending ? (
          <Skeleton className="h-10" />
        ) : (
          <select
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-2"
            value={scope.uf}
            onChange={(event) => update({ uf: event.target.value, municipio: '', option: '' })}
          >
            <option value="">{needsUf(scope.cargo) ? 'Selecione a UF' : 'Brasil'}</option>
            {stateList.map((state) => (
              <option key={state.sg_uf} value={state.sg_uf}>
                {state.nm_uf} ({state.sg_uf})
                {state.is_exterior ? ' — exterior' : ''}
              </option>
            ))}
          </select>
        )}
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-800">Município (código TSE)</span>
        <input
          className="w-full rounded-md border border-slate-300 px-2 py-2"
          value={munQ || scope.municipio}
          onChange={(event) => {
            const value = event.target.value
            setMunQ(value)
            if (/^\d{5}$/.test(value)) update({ municipio: value })
            if (!value) update({ municipio: '' })
          }}
          placeholder="Nome ou código de 5 dígitos"
          autoComplete="off"
        />
        {scope.municipio && (
          <button type="button" className="mt-1 text-xs text-atlas-700 underline" onClick={() => { setMunQ(''); update({ municipio: '' }) }}>
            Limpar município
          </button>
        )}
      </label>

      {debounced.length >= 2 && (
        <div className="sm:col-span-2 lg:col-span-4">
          {municipalities.isPending && <p className="text-xs text-slate-500">Buscando municípios…</p>}
          {municipalities.isError && <ErrorBlock error={municipalities.error} />}
          {municipalities.data && (
            <ul className="max-h-40 overflow-auto rounded-md border border-slate-200 bg-slate-50 text-sm">
              {municipalities.data.data.map((mun) => (
                <li key={mun.cd_municipio_tse}>
                  <button
                    type="button"
                    className="w-full px-3 py-1.5 text-left hover:bg-atlas-50"
                    onClick={() => {
                      update({ municipio: mun.cd_municipio_tse, uf: mun.sg_uf })
                      setMunQ(`${mun.nm_municipio} (${mun.cd_municipio_tse})`)
                    }}
                  >
                    {mun.nm_municipio} — {mun.sg_uf} · TSE {mun.cd_municipio_tse}
                    {mun.is_exterior ? ' · exterior' : ''}
                  </button>
                </li>
              ))}
              {municipalities.data.data.length === 0 && (
                <li className="px-3 py-2 text-slate-500">Nenhum município encontrado para esta busca.</li>
              )}
            </ul>
          )}
        </div>
      )}

      {showMode && (
        <fieldset className="sm:col-span-2 lg:col-span-4">
          <legend className="mb-1 text-sm font-medium text-slate-800">Modo do mapa</legend>
          <div className="flex flex-wrap gap-3 text-sm">
            <label className="inline-flex items-center gap-1.5">
              <input type="radio" name="modo" checked={scope.modo === 'leader'} onChange={() => update({ modo: 'leader' })} />
              Líder por município
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input type="radio" name="modo" checked={scope.modo === 'candidate'} onChange={() => update({ modo: 'candidate' })} />
              Intensidade de uma candidatura
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input type="radio" name="modo" checked={scope.modo === 'margin'} onChange={() => update({ modo: 'margin' })} />
              Diferença 1º–2º
            </label>
          </div>
        </fieldset>
      )}
    </form>
  )
}
