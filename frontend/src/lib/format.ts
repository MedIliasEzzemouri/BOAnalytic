/** Formatage de date court : 12 mai 2026. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Date + heure : 12 mai 2026, 14:32. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Heure seule : 14:32. */
export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

/** Score 0-1 → pourcentage entier. */
export function formatScore(score: number | null | undefined): string {
  if (score == null) return '—'
  const pct = score <= 1 ? score * 100 : score
  return `${Math.round(pct)}%`
}

/** Score 0-1 → nombre 0-100. */
export function scorePercent(score: number | null | undefined): number {
  if (score == null) return 0
  return Math.round((score <= 1 ? score * 100 : score))
}

const MOIS = [
  'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
  'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
]

export function moisLabel(mois: number): string {
  return MOIS[mois - 1] ?? String(mois)
}
