import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { alertesApi, bulletinsApi, errorMessage } from '../api/client'
import type { Alerte, AlertePriorite, AlerteStatut, Bulletin } from '../types'
import { ErrorBox, EmptyState } from '../components/ui'
import { TableSkeleton } from '../components/Skeleton'
import { PrioriteBadge, StatutAlerteBadge } from '../components/badges'
import { formatDate, formatTime, scorePercent } from '../lib/format'
import PageHeader from '../components/PageHeader'
import Icon from '../components/Icon'

const STATUTS: Array<{ key: AlerteStatut | 'tous'; label: string }> = [
  { key: 'tous', label: 'Tous' },
  { key: 'nouvelle', label: 'Nouvelle' },
  { key: 'vue', label: 'Vue' },
  { key: 'traitee', label: 'Traitée' },
  { key: 'ignoree', label: 'Ignorée' },
]

const PRIORITES: Array<{ key: AlertePriorite | 'tous'; label: string }> = [
  { key: 'tous', label: 'Tous' },
  { key: 'haute', label: 'Haute' },
  { key: 'moyenne', label: 'Moyenne' },
  { key: 'basse', label: 'Basse' },
]

const COLS = ['Score', 'Priorité', 'Nom détecté', 'Tier', 'Type', 'Statut', 'Date', '']

function scoreColor(pct: number): string {
  if (pct >= 90) return 'bg-green-600'
  if (pct >= 75) return 'bg-yellow-600'
  return 'bg-clay'
}

/** Identifiant du bulletin source d'une alerte. */
function bulletinIdOf(a: Alerte): number | null {
  return a.article_entreprise?.bulletin_id ?? a.article_mahakim?.bulletin_id ?? null
}

function FilterChips<T extends string>({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string
  options: Array<{ key: T; label: string }>
  value: T
  onChange: (v: T) => void
}) {
  return (
    <fieldset>
      <legend className="mb-3 font-label-md text-label-md uppercase tracking-wider text-secondary">
        {legend}
      </legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button
            key={o.key}
            type="button"
            onClick={() => onChange(o.key)}
            aria-pressed={value === o.key}
            className={`min-h-[36px] rounded border px-3 py-1.5 font-label-md transition-colors duration-200 ${
              value === o.key
                ? 'border-outline-variant bg-surface-container-high text-on-surface'
                : 'border-outline-variant text-secondary hover:bg-surface-container-low'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

export default function Alertes() {
  const navigate = useNavigate()
  const [alertes, setAlertes] = useState<Alerte[]>([])
  const [bulletins, setBulletins] = useState<Bulletin[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [statut, setStatut] = useState<AlerteStatut | 'tous'>('tous')
  const [priorite, setPriorite] = useState<AlertePriorite | 'tous'>('tous')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const PAGE_SIZE = 50

  useEffect(() => {
    setLoading(true)
    const params: { statut?: string; priorite?: string } = {}
    if (statut !== 'tous') params.statut = statut
    if (priorite !== 'tous') params.priorite = priorite
    alertesApi
      .list(params)
      .then(setAlertes)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [statut, priorite])

  useEffect(() => { setPage(1) }, [statut, priorite, search])

  // Bulletins : pour afficher numéro + date de chaque BO source.
  useEffect(() => {
    bulletinsApi
      .list()
      .then(setBulletins)
      .catch(() => setBulletins([]))
  }, [])

  const bulletinMap = useMemo(() => {
    const m = new Map<number, Bulletin>()
    bulletins.forEach((b) => m.set(b.id, b))
    return m
  }, [bulletins])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return alertes
    return alertes.filter(
      (a) =>
        a.nom_detecte.toLowerCase().includes(q) || a.nom_tier.toLowerCase().includes(q),
    )
  }, [alertes, search])


  const nouvelles = alertes.filter((a) => a.statut === 'nouvelle').length

  // Pagination sur les alertes (flattened, avant regroupement par BO)
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageStart = (page - 1) * PAGE_SIZE
  const pageEnd = pageStart + PAGE_SIZE
  const filteredPage = filtered.slice(pageStart, pageEnd)

  // Regroupe seulement les alertes de la page courante
  const groupes = useMemo(() => {
    const map = new Map<number | 'none', typeof filteredPage>()
    for (const a of filteredPage) {
      const key = bulletinIdOf(a) ?? 'none'
      const list = map.get(key)
      if (list) list.push(a)
      else map.set(key, [a])
    }
    return Array.from(map.entries()).sort(([kx], [ky]) => {
      if (kx === 'none') return 1
      if (ky === 'none') return -1
      const dx = bulletinMap.get(kx as number)?.date_publication ?? ''
      const dy = bulletinMap.get(ky as number)?.date_publication ?? ''
      if (dx !== dy) return dy.localeCompare(dx)
      return (ky as number) - (kx as number)
    })
  }, [filteredPage, bulletinMap])

  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto w-full max-w-container-max">
        <PageHeader
          title="Alertes"
          subtitle={
            <>
              {alertes.length} alerte{alertes.length > 1 ? 's' : ''} au total ·{' '}
              <span className="font-bold text-primary">
                {nouvelles} nouvelle{nouvelles > 1 ? 's' : ''}
              </span>{' '}
              à traiter · classées par bulletin officiel d'origine.
            </>
          }
        />

        {/* Filtres */}
        <section
          aria-label="Filtres"
          className="mb-8 rounded-lg border border-outline-variant bg-surface-container-lowest p-4"
        >
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <FilterChips legend="Statut" options={STATUTS} value={statut} onChange={setStatut} />
            </div>
            <div className="lg:col-span-3">
              <FilterChips
                legend="Priorité"
                options={PRIORITES}
                value={priorite}
                onChange={setPriorite}
              />
            </div>
            <div className="lg:col-span-5">
              <label
                htmlFor="rech-alerte"
                className="mb-3 block font-label-md text-label-md uppercase tracking-wider text-secondary"
              >
                Recherche partenaire / nom détecté
              </label>
              <div className="relative">
                <Icon
                  name="search"
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[20px] text-secondary"
                />
                <input
                  id="rech-alerte"
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Nom d'entité, partenaire…"
                  className="w-full rounded border border-outline-variant bg-limestone py-2 pl-10 pr-3 font-body-md text-ink outline-none transition-colors focus:border-primary"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Données groupées par BO */}
        <section className="overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest">
          {loading ? (
            <TableSkeleton rows={6} cols={7} />
          ) : error ? (
            <div className="p-4">
              <ErrorBox message={error} />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon="notifications_off"
              title="Aucune alerte"
              hint="Aucune alerte ne correspond à ces filtres."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse text-left">
                <caption className="sr-only">
                  Alertes de veille juridique groupées par bulletin officiel
                </caption>
                <thead>
                  <tr className="hairline-b bg-surface-container-low/50">
                    {COLS.map((h, i) => (
                      <th
                        key={i}
                        scope="col"
                        className="px-6 py-4 font-label-md text-label-md uppercase tracking-wider text-secondary"
                      >
                        {h || <span className="sr-only">Action</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                {groupes.map(([key, items]) => {
                  const bulletin = key === 'none' ? null : bulletinMap.get(key)
                  return (
                    <tbody key={String(key)}>
                      {/* En-tête de groupe — bulletin officiel d'origine */}
                      <tr>
                        <td
                          colSpan={COLS.length}
                          className="border-y border-outline-variant bg-surface-container px-6 py-3"
                        >
                          <div className="flex flex-wrap items-center gap-3">
                            <Icon
                              name="description"
                              className="text-[20px] text-slate"
                            />
                            <span className="font-headline-md text-[16px] font-bold text-ink">
                              {key === 'none'
                                ? 'Sans bulletin source'
                                : bulletin
                                  ? `Bulletin Officiel n°${bulletin.numero}`
                                  : `Bulletin #${key}`}
                            </span>
                            {bulletin && (
                              <span className="font-body-sm text-slate">
                                · publié le {formatDate(bulletin.date_publication)}
                              </span>
                            )}
                            <span className="ml-auto rounded-full bg-ink px-2.5 py-0.5 font-label-caps text-[10px] uppercase tracking-wider text-surface">
                              {items.length} alerte{items.length > 1 ? 's' : ''}
                            </span>
                          </div>
                        </td>
                      </tr>
                      {items.map((a) => {
                        const pct = scorePercent(a.score_similarite)
                        return (
                          <tr
                            key={a.id}
                            onClick={() => navigate(`/alertes/${a.id}`)}
                            className="hairline-b cursor-pointer transition-colors hover:bg-surface-container-low/40"
                          >
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-3">
                                <div className="h-1.5 w-12 overflow-hidden rounded-full bg-secondary-fixed">
                                  <div
                                    className={`h-full ${scoreColor(pct)}`}
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="font-label-md">{pct}%</span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <PrioriteBadge priorite={a.priorite} />
                            </td>
                            <td className="px-6 py-4 font-semibold uppercase">{a.nom_detecte}</td>
                            <td className="px-6 py-4 uppercase text-secondary">{a.nom_tier}</td>
                            <td className="px-6 py-4 text-secondary">{a.type_annonce ?? '—'}</td>
                            <td className="px-6 py-4">
                              <StatutAlerteBadge statut={a.statut} />
                            </td>
                            <td className="px-6 py-4 font-caption text-secondary">
                              {formatDate(a.created_at)}
                              <br />
                              {formatTime(a.created_at)}
                            </td>
                            <td className="px-6 py-4 text-right">
                              <Link
                                to={`/alertes/${a.id}`}
                                onClick={(e) => e.stopPropagation()}
                                aria-label={`Voir le détail de l'alerte ${a.nom_detecte}`}
                                className="inline-flex items-center justify-end gap-1 rounded font-label-md text-on-surface hover:underline"
                              >
                                Voir
                                <Icon name="chevron_right" className="text-[16px]" />
                              </Link>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  )
                })}
              </table>
            </div>
          )}
          {!loading && !error && filtered.length > 0 && (
            <div className="hairline-t flex flex-col items-center gap-3 p-4 sm:flex-row sm:justify-between">
              <span className="font-caption text-caption text-secondary">
                {filtered.length} alerte{filtered.length > 1 ? 's' : ''} · page {page}/{totalPages}
              </span>
              {totalPages > 1 && (
                <AlertesPagination page={page} totalPages={totalPages} onChange={setPage} />
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function AlertesPagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  const delta = 2
  const left = Math.max(1, page - delta)
  const right = Math.min(totalPages, page + delta)
  const range: number[] = []
  for (let i = left; i <= right; i++) range.push(i)

  const btn = (active: boolean, disabled = false) =>
    `flex h-9 w-9 items-center justify-center rounded border font-label-md text-[13px] transition-colors
    ${disabled ? 'cursor-not-allowed border-outline-variant text-slate/40' : ''}
    ${active ? 'border-primary bg-primary text-white' : !disabled ? 'border-outline-variant text-secondary hover:bg-limestone' : ''}`

  return (
    <div className="flex items-center gap-1">
      <button type="button" disabled={page === 1} onClick={() => onChange(1)} className={btn(false, page === 1)} aria-label="Première">«</button>
      {left > 1 && <span className="px-1 text-slate">…</span>}
      {range.map((p) => (
        <button key={p} type="button" onClick={() => onChange(p)} className={btn(p === page)} aria-current={p === page ? 'page' : undefined}>{p}</button>
      ))}
      {right < totalPages && <span className="px-1 text-slate">…</span>}
      <button type="button" disabled={page === totalPages} onClick={() => onChange(totalPages)} className={btn(false, page === totalPages)} aria-label="Dernière">»</button>
    </div>
  )
}
