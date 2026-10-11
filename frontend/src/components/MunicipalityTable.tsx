import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import type { CandidateMunicipality, LeaderMunicipality } from '../api/types'
import { formatInt, formatPctShort } from '../lib/format'
import { TIE_COLOR, NO_DATA_COLOR, fillForLeaderRow } from '../lib/mapColors'

type SortKey = 'nm_municipio' | 'sg_uf' | 'pct' | 'votos'

function isLeader(row: LeaderMunicipality | CandidateMunicipality): row is LeaderMunicipality {
  return 'leader' in row
}

export function MunicipalityTable({
  rows,
  mode,
}: {
  rows: Array<LeaderMunicipality | CandidateMunicipality>
  mode: 'leader' | 'candidate' | 'margin'
}) {
  const [sort, setSort] = useState<SortKey>('nm_municipio')
  const [dir, setDir] = useState<'asc' | 'desc'>('asc')

  const sorted = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      const sign = dir === 'asc' ? 1 : -1
      if (sort === 'nm_municipio') return sign * a.nm_municipio.localeCompare(b.nm_municipio, 'pt-BR')
      if (sort === 'sg_uf') return sign * a.sg_uf.localeCompare(b.sg_uf, 'pt-BR')
      const pa = isLeader(a) ? (mode === 'margin' ? a.margin_pp : a.leader?.pct_validos) : a.pct_validos
      const pb = isLeader(b) ? (mode === 'margin' ? b.margin_pp : b.leader?.pct_validos) : b.pct_validos
      if (sort === 'pct') return sign * ((pa ?? -1) - (pb ?? -1))
      const va = isLeader(a) ? a.leader?.qt_votos_validos : a.qt_votos_validos
      const vb = isLeader(b) ? b.leader?.qt_votos_validos : b.qt_votos_validos
      return sign * ((va ?? -1) - (vb ?? -1))
    })
    return copy
  }, [rows, sort, dir, mode])

  function toggle(key: SortKey) {
    if (sort === key) setDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSort(key)
      setDir(key === 'nm_municipio' || key === 'sg_uf' ? 'asc' : 'desc')
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Municípios do recorte, alternativa acessível ao mapa</caption>
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-2 py-2"><button type="button" onClick={() => toggle('nm_municipio')}>Município</button></th>
            <th className="px-2 py-2"><button type="button" onClick={() => toggle('sg_uf')}>UF</button></th>
            <th className="px-2 py-2">Situação no mapa</th>
            <th className="px-2 py-2"><button type="button" onClick={() => toggle('votos')}>Votos válidos</button></th>
            <th className="px-2 py-2"><button type="button" onClick={() => toggle('pct')}>% dos votos válidos</button></th>
            <th className="px-2 py-2">Detalhe</th>
          </tr>
        </thead>
        <tbody>
          {sorted.filter((row) => !row.is_exterior).map((row) => {
            const leader = isLeader(row) ? row.leader : null
            const color = isLeader(row) ? fillForLeaderRow(row) : (row.pct_validos == null ? NO_DATA_COLOR : '#1d4ed8')
            const status = isLeader(row)
              ? row.tie
                ? 'Empate'
                : leader
                  ? leader.label
                  : 'Sem dados'
              : row.pct_validos == null
                ? 'Sem dados'
                : formatPctShort(row.pct_validos)
            const votos = isLeader(row) ? leader?.qt_votos_validos : row.qt_votos_validos
            const pct = isLeader(row) ? (mode === 'margin' ? row.margin_pp : leader?.pct_validos) : row.pct_validos
            return (
              <tr key={row.cd_municipio_tse} className="border-t border-slate-100">
                <td className="px-2 py-1.5">{row.nm_municipio}</td>
                <td className="px-2 py-1.5">{row.sg_uf}</td>
                <td className="px-2 py-1.5">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="inline-block h-3 w-3 rounded-sm ring-1 ring-slate-300"
                      style={{ background: isLeader(row) && row.tie ? TIE_COLOR : color }}
                      aria-hidden
                    />
                    {status}
                  </span>
                </td>
                <td className="px-2 py-1.5 tabular-nums">{formatInt(votos ?? null)}</td>
                <td className="px-2 py-1.5 tabular-nums">{formatPctShort(pct ?? null)}</td>
                <td className="px-2 py-1.5">
                  <Link
                    className="text-atlas-700 underline"
                    to={`/explorar?uf=${row.sg_uf}&municipio=${row.cd_municipio_tse}`}
                  >
                    Explorar
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
