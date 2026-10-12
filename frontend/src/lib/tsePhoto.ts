/** Foto oficial do TSE.
 * 2026 (verificado 2026-10-12): portal de resultados
 *   `https://resultados.tse.jus.br/oficial/ele2026/{cd_eleicao}/fotos/{ue}/{sq}.jpeg`
 * 2022: o mesmo caminho 404; o TSE publica JPEG no ZIP do CDN
 *   `foto_cand2022_{UE}_div.zip` (arquivo `F{UE}{sq}_div.jpg|jpeg`). A API extrai e serve em `/api/photos/...`.
 */
export function tseCandidatePhotoUrl(args: {
  ano?: number | string | null
  cdEleicao?: string | null
  sgUe?: string | null
  sqCandidato?: string | null
}): string | null {
  const ano = String(args.ano ?? '')
  const cd = String(args.cdEleicao ?? '').trim()
  const sq = String(args.sqCandidato ?? '').trim()
  const ue = String(args.sgUe ?? '').trim().toUpperCase()
  if (!/^\d{5,14}$/.test(sq)) return null
  if (!/^[A-Z]{2}$/.test(ue) && ue !== 'BR') return null
  if (ano === '2022') return `/api/photos/2022/${ue}/${sq}`
  if (ano !== '2026') return null
  if (!/^\d{3,6}$/.test(cd)) return null
  return `https://resultados.tse.jus.br/oficial/ele2026/${cd}/fotos/${ue.toLowerCase()}/${sq}.jpeg`
}
