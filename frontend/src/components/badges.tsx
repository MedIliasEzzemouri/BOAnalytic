import type { AlertePriorite, AlerteStatut, BulletinStatut } from '../types'

const STATUT_ALERTE: Record<AlerteStatut, { label: string; cls: string }> = {
  nouvelle: { label: 'Nouvelle', cls: 'bg-blue-100 text-blue-700 border-blue-200' },
  vue: { label: 'Vue', cls: 'bg-surface-container text-secondary border-outline-variant' },
  traitee: { label: 'Traitée', cls: 'bg-green-100 text-green-700 border-green-200' },
  ignoree: { label: 'Ignorée', cls: 'bg-surface-container text-outline border-outline-variant' },
}

export function StatutAlerteBadge({ statut }: { statut: AlerteStatut }) {
  const s = STATUT_ALERTE[statut] ?? STATUT_ALERTE.vue
  return (
    <span
      className={`inline-block rounded border px-2.5 py-0.5 font-label-md text-[11px] uppercase tracking-wider ${s.cls}`}
    >
      {s.label}
    </span>
  )
}

const PRIORITE: Record<AlertePriorite, { label: string; cls: string }> = {
  haute: { label: 'Haute', cls: 'border-primary text-primary' },
  moyenne: { label: 'Moyenne', cls: 'border-yellow-600 text-yellow-700' },
  basse: { label: 'Basse', cls: 'border-outline text-slate' },
}

export function PrioriteBadge({ priorite }: { priorite: AlertePriorite }) {
  const p = PRIORITE[priorite] ?? PRIORITE.basse
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 font-label-md text-[11px] uppercase ${p.cls}`}
    >
      {p.label}
    </span>
  )
}

const STATUT_BULLETIN: Record<BulletinStatut, { label: string; dot: string; text: string }> = {
  en_attente: { label: 'En attente', dot: 'bg-outline', text: 'text-slate' },
  en_cours: { label: 'En cours', dot: 'bg-yellow-500', text: 'text-yellow-700' },
  traite: { label: 'Traité', dot: 'bg-green-600', text: 'text-green-700' },
  erreur: { label: 'Erreur', dot: 'bg-error', text: 'text-error' },
}

export function StatutBulletinBadge({ statut }: { statut: BulletinStatut }) {
  const s = STATUT_BULLETIN[statut] ?? STATUT_BULLETIN.en_attente
  return (
    <span className={`flex items-center gap-2 font-body-md text-body-md ${s.text}`}>
      <span className={`h-2 w-2 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  )
}
