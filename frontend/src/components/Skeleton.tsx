/** Bloc de squelette générique. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton rounded ${className}`} aria-hidden="true" />
}

/** Squelette de tableau (lignes x colonnes). */
export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="p-4" role="status" aria-label="Chargement des données">
      <div className="mb-4 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex gap-4">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className="h-9 flex-1" />
            ))}
          </div>
        ))}
      </div>
      <span className="sr-only">Chargement…</span>
    </div>
  )
}

/** Squelette de grille de cartes. */
export function CardGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div
      className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
      role="status"
      aria-label="Chargement des données"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="border border-outline-variant bg-surface-container-lowest p-6">
          <div className="mb-4 flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
          <Skeleton className="h-8 w-full" />
        </div>
      ))}
      <span className="sr-only">Chargement…</span>
    </div>
  )
}
