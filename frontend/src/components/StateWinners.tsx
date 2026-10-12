import type { LeaderMunicipality } from '../api/types'
import { formatInt, formatPctShort } from '../lib/format'
import { CandidatePhoto } from './CandidatePhoto'

export function StateWinners({
  rows,
  ano,
  onSelectUf,
}: {
  rows: LeaderMunicipality[]
  ano: number
  onSelectUf: (uf: string) => void
}) {
  return (
    <div className="min-w-0 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-[48rem] text-left text-sm">
        <caption className="sr-only">Vencedor de votos válidos por UF</caption>
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">UF</th>
            <th className="px-3 py-2">Candidatura</th>
            <th className="px-3 py-2">Partido</th>
            <th className="px-3 py-2">Votos válidos</th>
            <th className="px-3 py-2">%</th>
            <th className="px-3 py-2">Situação oficial (TSE)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const leader = row.leader
            return (
              <tr key={row.sg_uf} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  <button type="button" className="font-semibold text-atlas-700 underline-offset-2 hover:underline" onClick={() => onSelectUf(row.sg_uf)}>
                    {row.nm_municipio} ({row.sg_uf})
                  </button>
                </td>
                <td className="px-3 py-2">
                  {leader ? (
                    <span className="inline-flex min-w-0 items-center gap-2">
                      <span className="inline-block h-3 w-3 shrink-0 rounded-sm ring-1 ring-slate-300" style={{ background: leader.color || '#94a3b8' }} aria-hidden />
                      <CandidatePhoto
                        name={leader.label}
                        ano={ano}
                        cdEleicao={leader.cd_eleicao}
                        sgUe={leader.sg_ue}
                        sqCandidato={leader.sq_candidato}
                        color={leader.color}
                        size={28}
                      />
                      <span className="min-w-0 truncate">{leader.label}</span>
                    </span>
                  ) : (
                    <span className="text-slate-500">sem dados</span>
                  )}
                </td>
                <td className="px-3 py-2">{leader?.sg_partido ?? '—'}</td>
                <td className="px-3 py-2 tabular-nums">{leader ? formatInt(leader.qt_votos_validos) : '—'}</td>
                <td className="px-3 py-2 tabular-nums">{leader ? formatPctShort(leader.pct_validos) : '—'}</td>
                <td className="px-3 py-2">{leader?.ds_sit_tot_turno ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
