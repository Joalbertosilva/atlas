/** Cores convencionais de leitura por partido. O TSE não publica paleta de candidatura. */
const PARTY_COLORS: Record<string, string> = {
  PT: '#E30613',
  PL: '#F5C400',
  PDT: '#FE0000',
  PSOL: '#FFCC00',
  PSDB: '#0080C8',
  MDB: '#00A859',
  UNIAO: '#00AEEF',
  PP: '#1E4D8C',
  REPUBLICANOS: '#0A2F8C',
  PSD: '#FF8A00',
  NOVO: '#F37021',
  PSB: '#E31C23',
  PCDOB: '#DA251C',
  REDE: '#00A99D',
  PV: '#006633',
  PSTU: '#ED1C24',
  PCB: '#CC0000',
  UP: '#7A0019',
  SOLIDARIEDADE: '#F68B1F',
  CIDADANIA: '#EC008C',
  AVANTE: '#ED3237',
  PODE: '#2D8C3C',
  PODEMOS: '#2D8C3C',
  PRD: '#1B4F9C',
  DC: '#0A5BA8',
  AGIR: '#1E5AA8',
  MOBILIZA: '#1B4B8C',
  PRTB: '#0033A0',
  PMB: '#00A0E0',
  PCO: '#8B0000',
  MISSAO: '#C2410C',
  PR: '#F5C400',
}

const NR_COLORS: Record<string, string> = {
  '10': '#0A2F8C',
  '11': '#1E4D8C',
  '12': '#FE0000',
  '13': '#E30613',
  '14': '#C2410C',
  '15': '#00A859',
  '16': '#ED1C24',
  '18': '#00A99D',
  '20': '#2D8C3C',
  '21': '#CC0000',
  '22': '#F5C400',
  '23': '#EC008C',
  '27': '#0A5BA8',
  '28': '#0033A0',
  '29': '#8B0000',
  '30': '#F37021',
  '33': '#1B4B8C',
  '36': '#1E5AA8',
  '40': '#E31C23',
  '43': '#006633',
  '44': '#00AEEF',
  '45': '#0080C8',
  '50': '#FFCC00',
  '55': '#FF8A00',
  '65': '#DA251C',
  '70': '#ED3237',
  '77': '#F68B1F',
  '80': '#7A0019',
}

export const PL_YELLOW = '#F5C400'
export const PT_RED = '#E30613'

function normParty(sg: string | null | undefined): string {
  return (sg || '')
    .toUpperCase()
    .replace(/[.\s]/g, '')
    .replace('UNIÃO', 'UNIAO')
    .replace('MISSÃO', 'MISSAO')
}

export function partyColor(sgPartido?: string | null, nrPartido?: string | null, fallback = '#16325c'): string {
  const key = normParty(sgPartido)
  if (key && PARTY_COLORS[key]) return PARTY_COLORS[key]
  const nr = (nrPartido || '').trim()
  if (nr && NR_COLORS[nr]) return NR_COLORS[nr]
  return fallback
}
