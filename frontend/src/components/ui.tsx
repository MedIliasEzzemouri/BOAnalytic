import type { ReactNode } from 'react'
import Icon from './Icon'

/** Indicateur de chargement plein conteneur. */
export function Spinner({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-20 text-slate"
      role="status"
      aria-live="polite"
    >
      <Icon name="progress_activity" className="animate-spin text-[32px] text-primary" />
      <span className="font-body-sm">{label}</span>
    </div>
  )
}

/** Bandeau d'erreur. */
export function ErrorBox({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded border border-error/30 bg-error-container p-3 text-on-error-container"
    >
      <Icon name="error" className="mt-[2px] text-[18px]" />
      <span className="font-body-md text-body-md">{message}</span>
    </div>
  )
}

/** État vide d'une liste / table. */
export function EmptyState({
  icon = 'inbox',
  title,
  hint,
  action,
}: {
  icon?: string
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <span className="mb-1 flex h-14 w-14 items-center justify-center rounded-full bg-surface-container-high">
        <Icon name={icon} className="text-[28px] text-outline" />
      </span>
      <p className="font-headline-md text-headline-md text-ink">{title}</p>
      {hint && <p className="max-w-sm font-body-sm text-slate">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

/** Carte simple (surface blanche bordée). */
export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={`border border-outline-variant bg-surface-container-lowest ${className}`}
    >
      {children}
    </div>
  )
}
