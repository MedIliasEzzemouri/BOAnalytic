import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: ReactNode
  /** Actions affichées à droite (boutons…). */
  actions?: ReactNode
  /** Titre de petite taille (sous-pages) plutôt que `display`. */
  compact?: boolean
}

/** En-tête de page cohérent sur toute l'application. */
export default function PageHeader({
  title,
  subtitle,
  actions,
  compact = false,
}: PageHeaderProps) {
  return (
    <header className="mb-8 flex flex-col items-start justify-between gap-4 border-b border-outline-variant pb-6 md:flex-row md:items-end">
      <div>
        <h1
          className={
            compact
              ? 'font-headline-lg text-headline-lg text-ink'
              : 'font-display text-display text-ink'
          }
        >
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 font-body-md text-body-md text-slate">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-3">{actions}</div>}
    </header>
  )
}
