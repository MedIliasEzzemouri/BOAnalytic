import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { alertesApi, bulletinsApi, errorMessage, fetchScreenshot } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { Alerte, ArticleEntreprise, ArticleMahakim, Bulletin } from '../types'
import { ErrorBox, EmptyState } from '../components/ui'
import { formatDate } from '../lib/format'
import Modal from '../components/Modal'
import Icon from '../components/Icon'

type Section = 'legale' | 'judiciaire'

interface Row {
  id: number
  seq: number
  entite: string | null
  section: Section
  type: string | null
  texte: string
  page: number | null
  tribunal?: string | null
}

const TYPE_LABEL: Record<string, string> = {
  creation: 'Création',
  modification: 'Modification',
  cession: 'Cession',
  liquidation: 'Liquidation',
  tsfiya_qadaiya: 'Liq. judiciaire',
  taswiya_qadaiya: 'Redressement',
  difficultes: 'Difficultés',
  faillite: 'Faillite',
  dissolution_liquidation: 'Dissolution',
  saisie: 'Saisie',
  judiciaire: 'Judiciaire',
}

const PAGE_SIZE = 50

export default function BulletinDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const bulletinId = Number(id)
  const { canManageBulletins } = useAuth()

  const [bulletin, setBulletin] = useState<Bulletin | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [alertMap, setAlertMap] = useState<Map<string, Alerte>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retraitBusy, setRetraitBusy] = useState(false)

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<Section | 'tous'>('tous')
  const [etatFilter, setEtatFilter] = useState<'tous' | 'acceptee' | 'rejetee'>('tous')
  const [page, setPage] = useState(1)
  const [preview, setPreview] = useState<Row | null>(null)
  const [ignored, setIgnored] = useState<Set<string>>(new Set())

  // Screenshot state for preview modal
  const [shotSrc, setShotSrc] = useState<string | null>(null)
  const [shotState, setShotState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const shotCleanup = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    // Load bulletin + articles (blocking), alertes non-blocking
    Promise.all([
      bulletinsApi.get(bulletinId),
      bulletinsApi.articles(bulletinId, { limit: 2000 }),
    ])
      .then(([b, articles]) => {
        setBulletin(b)
        const legales: Row[] = articles.legales.map((a: ArticleEntreprise, i: number) => ({
          id: a.id,
          seq: i + 1,
          entite: a.nom_entreprise,
          section: 'legale',
          type: a.type_annonce ?? null,
          texte: a.texte_annonce,
          page: a.page_bulletin ?? null,
        }))
        const judiciaires: Row[] = articles.judiciaires.map((a: ArticleMahakim, i: number) => ({
          id: a.id,
          seq: legales.length + i + 1,
          entite: a.nom_entreprise,
          section: 'judiciaire',
          type: a.type_procedure ?? null,
          texte: a.texte_annonce,
          page: a.page_bulletin ?? null,
          tribunal: a.tribunal,
        }))
        setRows([...legales, ...judiciaires])
        // Fetch alertes separately — don't block main render
        alertesApi.list({ bulletin_id: bulletinId })
          .then((alertes) => {
            const map = new Map<string, Alerte>()
            for (const a of alertes) {
              if (a.article_entreprise?.id) map.set(`legale-${a.article_entreprise.id}`, a)
              if (a.article_mahakim?.id) map.set(`judiciaire-${a.article_mahakim.id}`, a)
            }
            setAlertMap(map)
          })
          .catch(() => { /* alertes non-critical, ignore */ })
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [id, bulletinId])

  useEffect(() => { setPage(1) }, [search, typeFilter, etatFilter])

  // Load screenshot when preview changes
  useEffect(() => {
    // Cleanup previous
    if (shotCleanup.current) { shotCleanup.current(); shotCleanup.current = null }
    if (!preview) { setShotSrc(null); setShotState('idle'); return }

    let cancelled = false
    let objectUrl: string | null = null
    setShotState('loading')
    setShotSrc(null)

    const kind = preview.section === 'legale' ? 'entreprise' : 'mahakim'
    const timer = setTimeout(() => { if (!cancelled) { cancelled = true; setShotState('error') } }, 12000)

    fetchScreenshot(kind, preview.id)
      .then((url) => {
        clearTimeout(timer)
        if (cancelled) { URL.revokeObjectURL(url); return }
        objectUrl = url
        setShotSrc(url)
        setShotState('ok')
      })
      .catch(() => { clearTimeout(timer); if (!cancelled) setShotState('error') })

    shotCleanup.current = () => {
      cancelled = true
      clearTimeout(timer)
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
    return () => { if (shotCleanup.current) { shotCleanup.current(); shotCleanup.current = null } }
  }, [preview])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return rows.filter((r) => {
      const key = `${r.section}-${r.id}`
      if (typeFilter !== 'tous' && r.section !== typeFilter) return false
      if (etatFilter === 'acceptee' && (!r.entite || ignored.has(key))) return false
      if (etatFilter === 'rejetee' && (r.entite && !ignored.has(key))) return false
      if (q && !(r.entite ?? '').toLowerCase().includes(q)) return false
      return true
    })
  }, [rows, search, typeFilter, etatFilter, ignored])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageSlice = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="font-body-md text-slate">Chargement des annonces…</span>
      </div>
    )
  }

  if (error) {
    return <div className="p-gutter"><ErrorBox message={error} /></div>
  }

  if (!bulletin) return null

  const acceptees = rows.filter((r) => r.entite).length
  const rejetees = rows.filter((r) => !r.entite).length

  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto w-full max-w-container-max">

        {/* Header */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="material-symbols-rounded text-[28px] text-primary">list_alt</span>
            <h1 className="font-headline-lg text-[24px] font-bold text-primary">
              Annonces du Bulletin #{bulletin.numero}
            </h1>
          </div>
          <button
            type="button"
            onClick={() => navigate('/bulletins')}
            className="flex w-fit items-center gap-2 rounded border border-outline-variant px-4 py-2 font-label-md text-slate transition-colors hover:bg-limestone hover:text-ink"
          >
            <Icon name="arrow_back" className="text-[18px]" />
            Retour
          </button>
        </div>

        {/* Pipeline status banner */}
        {bulletin.statut === 'en_attente' && (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-5 py-3 font-body-md text-amber-700">
            <Icon name="schedule" className="text-[20px]" />
            <span className="flex-1">Pipeline ML en attente — le traitement va démarrer automatiquement.</span>
            {canManageBulletins && (
              <button
                type="button"
                disabled={retraitBusy}
                onClick={async () => {
                  setRetraitBusy(true)
                  try {
                    const updated = await bulletinsApi.retraiter(bulletinId)
                    setBulletin(updated)
                  } catch {/* ignore */} finally { setRetraitBusy(false) }
                }}
                className="flex items-center gap-1.5 rounded border border-amber-300 bg-white px-3 py-1.5 text-[12px] font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50"
              >
                <Icon name={retraitBusy ? 'autorenew' : 'play_arrow'} className={`text-[15px] ${retraitBusy ? 'animate-spin' : ''}`} />
                Lancer maintenant
              </button>
            )}
          </div>
        )}
        {bulletin.statut === 'en_cours' && (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-5 py-3 font-body-md text-blue-700">
            <Icon name="autorenew" className="animate-spin text-[20px]" />
            <span className="flex-1">Pipeline ML en cours de traitement — les annonces apparaîtront automatiquement.</span>
            {canManageBulletins && (
              <button
                type="button"
                disabled={retraitBusy}
                onClick={async () => {
                  setRetraitBusy(true)
                  try {
                    const updated = await bulletinsApi.retraiter(bulletinId)
                    setBulletin(updated)
                  } catch {/* ignore */} finally { setRetraitBusy(false) }
                }}
                className="flex items-center gap-1.5 rounded border border-blue-300 bg-white px-3 py-1.5 text-[12px] font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50"
              >
                <Icon name={retraitBusy ? 'autorenew' : 'replay'} className={`text-[15px] ${retraitBusy ? 'animate-spin' : ''}`} />
                Relancer
              </button>
            )}
          </div>
        )}
        {bulletin.statut === 'erreur' && (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-5 py-3 font-body-md text-red-700">
            <Icon name="error" className="text-[20px]" />
            <span className="flex-1">Erreur de traitement ML.</span>
            {canManageBulletins && (
              <button
                type="button"
                disabled={retraitBusy}
                onClick={async () => {
                  setRetraitBusy(true)
                  try {
                    const updated = await bulletinsApi.retraiter(bulletinId)
                    setBulletin(updated)
                  } catch {/* ignore */} finally { setRetraitBusy(false) }
                }}
                className="flex items-center gap-1.5 rounded border border-red-300 bg-white px-3 py-1.5 text-[12px] font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50"
              >
                <Icon name={retraitBusy ? 'autorenew' : 'replay'} className={`text-[15px] ${retraitBusy ? 'animate-spin' : ''}`} />
                Relancer
              </button>
            )}
          </div>
        )}

        {/* Info strip */}
        <div className="mb-6 flex flex-wrap gap-4 rounded-lg border border-outline-variant bg-surface-container-lowest px-5 py-4 text-sm text-slate">
          <span><strong className="text-ink">Publié :</strong> {formatDate(bulletin.date_publication)}</span>
          <span><strong className="text-ink">Pages :</strong> {bulletin.nb_pages}</span>
          <span><strong className="text-ink">Légales :</strong> {bulletin.nb_annonces_legales}</span>
          <span><strong className="text-ink">Judiciaires :</strong> {bulletin.nb_annonces_judiciaires}</span>
          <span className="text-green-600"><strong>Acceptées :</strong> {acceptees}</span>
          <span className="text-red-600"><strong>Rejetées :</strong> {rejetees}</span>
        </div>

        {/* Filters */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:w-80">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrer par entité…"
              className="w-full rounded border border-outline-variant bg-white py-2.5 pl-10 pr-4 font-body-md text-ink outline-none transition-colors placeholder:text-slate/60 focus:border-primary"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {(['tous', 'legale', 'judiciaire'] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setTypeFilter(v)}
                className={`rounded-full px-4 py-1.5 font-label-md text-[12px] transition-colors ${
                  typeFilter === v
                    ? v === 'legale' ? 'bg-blue-500 text-white'
                    : v === 'judiciaire' ? 'bg-red-500 text-white'
                    : 'bg-primary text-white'
                    : 'border border-outline-variant text-secondary hover:bg-limestone'
                }`}
              >
                {v === 'tous' ? 'Tous' : v === 'legale' ? 'Légales' : 'Judiciaires'}
              </button>
            ))}
            <span className="mx-1 text-outline-variant">|</span>
            {(['tous', 'acceptee', 'rejetee'] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setEtatFilter(v)}
                className={`rounded-full px-4 py-1.5 font-label-md text-[12px] transition-colors ${
                  etatFilter === v
                    ? v === 'acceptee' ? 'bg-green-500 text-white'
                    : v === 'rejetee' ? 'bg-red-500 text-white'
                    : 'bg-primary text-white'
                    : 'border border-outline-variant text-secondary hover:bg-limestone'
                }`}
              >
                {v === 'tous' ? 'Tous états' : v === 'acceptee' ? 'Acceptées' : 'Rejetées/Ignorées'}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="rounded-lg border border-outline-variant bg-white">
          {filtered.length === 0 ? (
            <EmptyState icon="domain" title="Aucune annonce" hint="Modifiez les filtres." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left">
                <caption className="sr-only">Annonces du bulletin</caption>
                <thead>
                  <tr className="border-b border-outline-variant bg-surface-container-low font-label-md text-[11px] uppercase tracking-wider text-secondary">
                    <th className="px-5 py-3 w-16">ID</th>
                    <th className="px-5 py-3">Entité</th>
                    <th className="px-5 py-3 w-28">Type</th>
                    <th className="px-5 py-3 w-36">Partenaire</th>
                    <th className="px-5 py-3 w-28">État</th>
                    <th className="px-5 py-3 w-24 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant font-body-md text-on-surface">
                  {pageSlice.map((r) => {
                    const key = `${r.section}-${r.id}`
                    const alerte = alertMap.get(key)
                    return (
                    <tr
                      key={key}
                      onClick={() => alerte ? navigate(`/alertes/${alerte.id}`) : setPreview(r)}
                      className="cursor-pointer hover:bg-surface-variant/20"
                    >
                      <td className="px-5 py-3 font-body-sm text-slate">{r.seq}</td>
                      <td className="px-5 py-3 font-medium text-ink">
                        {r.entite ?? <span className="italic text-slate/60">—</span>}
                      </td>
                      <td className="px-5 py-3">
                        <span className={`inline-flex items-center rounded px-2.5 py-1 text-[11px] font-bold uppercase ${
                          r.section === 'legale'
                            ? 'bg-blue-100 text-blue-600'
                            : 'bg-red-100 text-red-600'
                        }`}>
                          {r.section === 'legale' ? 'Légale' : 'Judiciaire'}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        {alerte ? (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700 border border-amber-200">
                            <Icon name="link" className="text-[13px]" />
                            {alerte.nom_tier}
                          </span>
                        ) : (
                          <span className="text-[12px] text-slate/40">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {ignored.has(`${r.section}-${r.id}`) ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-[12px] font-semibold text-slate-500">
                            <Icon name="do_not_disturb_on" className="text-[14px]" />
                            Ignorée
                          </span>
                        ) : r.entite ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-[12px] font-semibold text-green-700">
                            <Icon name="check_circle" className="text-[14px]" />
                            Acceptée
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-[12px] font-semibold text-red-600">
                            <Icon name="cancel" className="text-[14px]" />
                            Rejetée
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => setPreview(r)}
                          aria-label="Voir le texte de l'annonce"
                          className="flex h-9 w-9 items-center justify-center rounded border border-outline-variant text-slate transition-colors hover:border-primary hover:text-primary ml-auto"
                        >
                          <Icon name="visibility" className="text-[18px]" />
                        </button>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <Pagination page={page} totalPages={totalPages} onChange={setPage} />
        )}
      </div>

      {/* Article analysis modal */}
      {preview && (() => {
        const key = `${preview.section}-${preview.id}`
        const isIgnored = ignored.has(key)
        const directInfoQuery = encodeURIComponent(preview.entite ?? '')
        return (
          <Modal title={preview.entite ?? "Analyse de l'annonce"} onClose={() => setPreview(null)} size="max-w-4xl">
            <div className="flex flex-col gap-4 p-md">

              {/* Badges + vérification externe */}
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-2.5 py-1 text-[11px] font-bold uppercase ${
                  preview.section === 'legale' ? 'bg-blue-100 text-blue-600' : 'bg-red-100 text-red-600'
                }`}>
                  {preview.section === 'legale' ? 'Légale' : 'Judiciaire'}
                </span>
                {preview.type && (
                  <span className="rounded bg-surface-container px-2.5 py-1 text-[11px] font-semibold uppercase text-secondary">
                    {TYPE_LABEL[preview.type] ?? preview.type}
                  </span>
                )}
                {preview.page && (
                  <span className="rounded bg-limestone px-2.5 py-1 text-[11px] text-slate">
                    Page {preview.page}
                  </span>
                )}
                {preview.tribunal && (
                  <span className="rounded bg-limestone px-2.5 py-1 text-[11px] text-slate">
                    {preview.tribunal}
                  </span>
                )}
                {isIgnored && (
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-500">
                    Ignorée
                  </span>
                )}
              </div>

              {/* Annonce du BO — scan PDF ou texte brut */}
              <div>
                <p className="mb-2 font-label-caps text-[10px] uppercase tracking-wider text-slate">Annonce du BO</p>
                <div className="min-h-[200px] rounded border border-outline-variant bg-limestone">
                  {shotState === 'loading' && (
                    <div className="flex h-48 flex-col items-center justify-center gap-3 text-slate">
                      <Icon name="progress_activity" className="animate-spin text-[32px] text-primary" />
                      <span className="font-body-sm text-[12px]">Génération de la capture…</span>
                    </div>
                  )}
                  {shotState === 'ok' && shotSrc && (
                    <img
                      src={shotSrc}
                      alt={`Annonce BO — ${preview.entite}`}
                      className="w-full rounded object-contain"
                    />
                  )}
                  {(shotState === 'error' || shotState === 'idle') && (
                    preview.texte ? (
                      <div className="max-h-[40vh] overflow-y-auto p-4">
                        <p className="whitespace-pre-wrap font-body-md text-[13px] leading-relaxed text-ink">{preview.texte}</p>
                      </div>
                    ) : (
                      <div className="flex h-32 items-center justify-center">
                        <p className="italic text-slate text-[13px]">Texte non disponible.</p>
                      </div>
                    )
                  )}
                </div>
              </div>

              {/* Vérification externe */}
              {preview.entite && (
                <div className="rounded border border-outline-variant bg-surface-container-lowest p-3">
                  <p className="mb-2 font-label-caps text-[10px] uppercase tracking-wider text-slate">Vérification externe</p>
                  <p className="mb-3 font-body-sm text-[12px] text-secondary">
                    Confirme qu'il s'agit bien de cette société sur le registre de commerce marocain.
                  </p>
                  <a
                    href={`https://directinfo.ma/en/companies?search=${directInfoQuery}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded bg-ink px-4 py-2 font-label-md text-[13px] text-white hover:bg-ink/80"
                  >
                    <Icon name="open_in_new" className="text-[15px]" />
                    Vérifier sur DirectInfo.ma
                  </a>
                </div>
              )}

              {/* Décision */}
              <div className="flex items-center justify-between gap-3 border-t border-outline-variant pt-3">
                <p className="font-label-md text-[12px] text-slate">Décision pour cette annonce :</p>
                <div className="flex gap-2">
                  {isIgnored ? (
                    <button
                      type="button"
                      onClick={() => setIgnored((s) => { const n = new Set(s); n.delete(key); return n })}
                      className="flex items-center gap-2 rounded border border-green-300 bg-green-50 px-4 py-2 font-label-md text-[13px] text-green-700 hover:bg-green-100"
                    >
                      <Icon name="undo" className="text-[16px]" />
                      Rétablir
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => { setIgnored((s) => new Set(s).add(key)); setPreview(null) }}
                        className="flex items-center gap-2 rounded border border-slate-300 bg-slate-50 px-4 py-2 font-label-md text-[13px] text-slate-600 hover:bg-slate-200"
                      >
                        <Icon name="do_not_disturb_on" className="text-[16px]" />
                        Ignorer
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreview(null)}
                        className="flex items-center gap-2 rounded bg-primary px-4 py-2 font-label-md text-[13px] text-white hover:bg-primary/90"
                      >
                        <Icon name="check_circle" className="text-[16px]" />
                        Accepter
                      </button>
                    </>
                  )}
                </div>
              </div>

            </div>
          </Modal>
        )
      })()}
    </div>
  )
}

function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  // Show max 5 page numbers around current page
  const range: number[] = []
  const delta = 2
  const left = Math.max(1, page - delta)
  const right = Math.min(totalPages, page + delta)
  for (let i = left; i <= right; i++) range.push(i)

  const btnCls = (active: boolean, disabled = false) =>
    `flex h-10 w-10 items-center justify-center rounded border font-label-md text-[13px] transition-colors
    ${disabled ? 'cursor-not-allowed border-outline-variant text-slate/40' : ''}
    ${active ? 'border-primary bg-primary text-white' : !disabled ? 'border-outline-variant text-secondary hover:bg-limestone' : ''}`

  return (
    <div className="mt-5 flex items-center justify-center gap-1">
      <button
        type="button"
        disabled={page === 1}
        onClick={() => onChange(1)}
        className={btnCls(false, page === 1)}
        aria-label="Première page"
      >
        «
      </button>
      {left > 1 && <span className="px-1 text-slate">…</span>}
      {range.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onChange(p)}
          className={btnCls(p === page)}
          aria-current={p === page ? 'page' : undefined}
        >
          {p}
        </button>
      ))}
      {right < totalPages && <span className="px-1 text-slate">…</span>}
      <button
        type="button"
        disabled={page === totalPages}
        onClick={() => onChange(totalPages)}
        className={btnCls(false, page === totalPages)}
        aria-label="Dernière page"
      >
        »
      </button>
    </div>
  )
}
