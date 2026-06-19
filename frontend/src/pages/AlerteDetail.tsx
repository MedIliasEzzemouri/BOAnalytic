import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { alertesApi, errorMessage, fetchScreenshot } from '../api/client'
import type { Alerte } from '../types'
import { ErrorBox, Spinner } from '../components/ui'
import { PrioriteBadge, StatutAlerteBadge } from '../components/badges'
import { formatDate, formatScore } from '../lib/format'
import Button from '../components/Button'
import ConfirmDialog from '../components/ConfirmDialog'
import Icon from '../components/Icon'

type Decision = 'traitee' | 'ignoree'
type ShotState = 'loading' | 'ok' | 'error' | 'none'

export default function AlerteDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const alerteId = Number(id)

  const [alerte, setAlerte] = useState<Alerte | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)

  // Capture annotée du BO.
  const [shotSrc, setShotSrc] = useState<string | null>(null)
  const [shotState, setShotState] = useState<ShotState>('loading')

  // Navigation entre alertes.
  const [navIds, setNavIds] = useState<number[]>([])

  // Fenêtre de confirmation.
  const [confirmAction, setConfirmAction] = useState<Decision | null>(null)

  // ── Chargement de l'alerte ──
  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    alertesApi
      .get(alerteId)
      .then((a) => {
        setAlerte(a)
        setCommentaire(a.commentaire ?? '')
        if (a.statut === 'nouvelle') {
          alertesApi.marquerVue(alerteId).catch(() => undefined)
        }
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [id, alerteId])

  // ── Liste des IDs pour Précédent / Suivant ──
  useEffect(() => {
    alertesApi
      .list()
      .then((list) => setNavIds(list.map((a) => a.id)))
      .catch(() => setNavIds([]))
  }, [])

  // ── Capture du BO (téléchargée avec le JWT) ──
  useEffect(() => {
    if (!alerte) return
    const art = alerte.article_entreprise
    const artM = alerte.article_mahakim
    const kind: 'entreprise' | 'mahakim' | null = art
      ? 'entreprise'
      : artM
        ? 'mahakim'
        : null
    const articleId = art?.id ?? artM?.id ?? null
    if (!kind || articleId == null) {
      setShotState('none')
      return
    }

    let objectUrl: string | null = null
    let cancelled = false
    setShotState('loading')
    setShotSrc(null)

    // Timeout: if screenshot takes >12s, treat as error and show text fallback
    const timer = setTimeout(() => {
      if (!cancelled) {
        cancelled = true
        setShotState('error')
      }
    }, 12000)

    fetchScreenshot(kind, articleId)
      .then((url) => {
        clearTimeout(timer)
        if (cancelled) {
          URL.revokeObjectURL(url)
          return
        }
        objectUrl = url
        setShotSrc(url)
        setShotState('ok')
      })
      .catch(() => {
        clearTimeout(timer)
        if (!cancelled) setShotState('error')
      })

    return () => {
      cancelled = true
      clearTimeout(timer)
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [alerte])

  async function appliquer(statut: Decision) {
    if (!alerte) return
    setSaving(true)
    try {
      const updated = await alertesApi.update(alerte.id, { statut, commentaire })
      setConfirmAction(null)
      // Après une décision, on passe automatiquement à l'alerte suivante.
      const i = navIds.indexOf(alerteId)
      const next = i >= 0 && i < navIds.length - 1 ? navIds[i + 1] : null
      if (next != null) {
        navigate(`/alertes/${next}`)
      } else {
        setAlerte(updated)
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />
  if (error && !alerte) {
    return (
      <div className="p-gutter">
        <ErrorBox message={error} />
      </div>
    )
  }
  if (!alerte) return null

  const page = alerte.article_entreprise?.page_bulletin ?? alerte.article_mahakim?.page_bulletin ?? null
  const texte =
    alerte.article_entreprise?.texte_annonce ?? alerte.article_mahakim?.texte_annonce ?? null

  const idx = navIds.indexOf(alerteId)
  const prevId = idx > 0 ? navIds[idx - 1] : null
  const nextId = idx >= 0 && idx < navIds.length - 1 ? navIds[idx + 1] : null

  return (
    <div className="fade-in p-container-margin">
      <div className="mx-auto w-full max-w-container-max">
        {/* En-tête */}
        <div className="mb-space-lg flex flex-col items-start justify-between gap-4 border-b border-outline-variant pb-md md:flex-row md:items-end">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <PrioriteBadge priorite={alerte.priorite} />
              <StatutAlerteBadge statut={alerte.statut} />
              <span className="border border-outline-variant bg-surface px-2 py-1 font-label-caps text-label-caps text-slate">
                Alerte #{alerte.id}
              </span>
            </div>
            <h1 className="mb-1 font-headline-lg text-headline-lg text-ink">
              Détail de l'alerte : {alerte.nom_detecte}
            </h1>
            <p className="font-body-lg text-body-lg text-slate">
              Tier surveillé : {alerte.nom_tier} · Détectée le {formatDate(alerte.created_at)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              icon="chevron_left"
              disabled={prevId == null}
              onClick={() => prevId != null && navigate(`/alertes/${prevId}`)}
            >
              Précédent
            </Button>
            <Button
              variant="outline"
              disabled={nextId == null}
              onClick={() => nextId != null && navigate(`/alertes/${nextId}`)}
            >
              Suivant
              <Icon name="chevron_right" className="text-[18px]" />
            </Button>
            <Button variant="ghost" icon="list" onClick={() => navigate('/alertes')}>
              Liste
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-gutter">
            <ErrorBox message={error} />
          </div>
        )}

        <div className="grid grid-cols-1 gap-container-margin lg:grid-cols-12">
          {/* Colonne gauche */}
          <div className="flex flex-col gap-container-margin lg:col-span-7">
            {/* Annonce du BO */}
            <div className="flex flex-col border border-outline-variant bg-surface-container-lowest">
              <div className="flex items-center justify-between border-b border-outline-variant bg-surface px-md py-sm">
                <h2 className="font-headline-md text-headline-md text-ink">Annonce du BO</h2>
                {page != null && (
                  <span className="font-label-caps text-label-caps text-slate">Page {page}</span>
                )}
              </div>
              <div className="flex min-h-[400px] items-center justify-center bg-limestone p-md">
                {shotState === 'loading' && (
                  <div className="flex flex-col items-center gap-3 text-slate" role="status">
                    <Icon
                      name="progress_activity"
                      className="animate-spin text-[32px] text-primary"
                    />
                    <span className="font-body-sm">Génération de la capture…</span>
                  </div>
                )}
                {shotState === 'ok' && shotSrc && (
                  <img
                    alt={`Annonce du Bulletin Officiel encadrée — ${alerte.nom_detecte}`}
                    className="max-h-[600px] w-full border border-outline-variant bg-white object-contain"
                    src={shotSrc}
                  />
                )}
                {shotState === 'error' && (
                  <div className="flex flex-col gap-3 w-full">
                    {texte ? (
                      <div className="max-h-[400px] overflow-y-auto rounded border border-outline-variant bg-limestone p-4">
                        <p className="whitespace-pre-wrap font-body-md text-[13px] leading-relaxed text-ink">{texte}</p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2 text-center text-slate py-8">
                        <Icon name="image_not_supported" className="text-[40px] text-outline" />
                        <p className="font-body-sm">Capture indisponible — PDF introuvable.</p>
                      </div>
                    )}
                  </div>
                )}
                {shotState === 'none' && (
                  <div className="flex flex-col items-center gap-2 text-center text-slate">
                    <Icon name="hide_image" className="text-[40px] text-outline" />
                    <p className="font-body-sm">Aucune annonce source liée à cette alerte.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Texte brut */}
            {texte && (
              <div className="border border-outline-variant bg-surface-container-lowest">
                <div className="border-b border-outline-variant bg-surface px-md py-sm">
                  <h2 className="font-headline-md text-headline-md text-ink">
                    Texte brut extrait
                  </h2>
                </div>
                <div className="p-md">
                  <div className="max-h-72 overflow-y-auto border border-outline-variant bg-limestone p-3 font-body-sm leading-relaxed text-ink">
                    {texte}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Colonne droite */}
          <div className="flex flex-col gap-container-margin lg:col-span-5">
            {/* Score */}
            <div className="flex items-center justify-between border border-outline-variant bg-surface-container-lowest p-md">
              <div>
                <h2 className="mb-1 font-label-caps text-label-caps text-slate">
                  Score de confiance IA
                </h2>
                <div className="flex items-end gap-2">
                  <span className="font-headline-xl text-headline-xl text-ink">
                    {formatScore(alerte.score_similarite)}
                  </span>
                  <span className="pb-2 font-body-sm text-body-sm text-slate">
                    Similarité de nom
                  </span>
                </div>
              </div>
            </div>

            {/* Comparaison */}
            <div className="overflow-hidden border border-outline-variant bg-surface-container-lowest">
              <div className="border-b border-outline-variant bg-surface px-md py-sm">
                <h2 className="font-headline-md text-headline-md text-ink">
                  Comparaison des données
                </h2>
              </div>
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-outline-variant bg-surface-container-low">
                    <th scope="col" className="p-3 pl-md font-label-caps text-label-caps text-slate">
                      Attribut
                    </th>
                    <th scope="col" className="p-3 font-label-caps text-label-caps text-slate">
                      Détecté (BO)
                    </th>
                    <th scope="col" className="p-3 pr-md font-label-caps text-label-caps text-slate">
                      Base partenaire
                    </th>
                  </tr>
                </thead>
                <tbody className="font-body-sm text-body-sm">
                  <tr className="border-b border-outline-variant bg-surface-container">
                    <td className="py-3 pl-md font-medium text-ink">Nom</td>
                    <td className="py-3 font-bold text-clay">{alerte.nom_detecte}</td>
                    <td className="py-3 pr-md font-bold text-slate">{alerte.nom_tier}</td>
                  </tr>
                  <tr className="border-b border-outline-variant">
                    <td className="py-3 pl-md font-medium text-ink">Type</td>
                    <td className="py-3 text-ink">{alerte.type_annonce ?? '—'}</td>
                    <td className="py-3 pr-md text-ink">{alerte.tier?.type_tier ?? '—'}</td>
                  </tr>
                  <tr>
                    <td className="py-3 pl-md font-medium text-ink">Localisation</td>
                    <td className="py-3 italic text-slate">
                      {page != null ? `Page : ${page}` : '—'}
                    </td>
                    <td className="py-3 pr-md text-ink">{alerte.tier?.ville ?? '—'}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Verification externe sur DirectInfo */}
            <div className="border border-outline-variant bg-surface-container-lowest">
              <div className="border-b border-outline-variant bg-surface px-md py-sm">
                <h2 className="font-headline-md text-headline-md text-ink">
                  Vérification externe
                </h2>
              </div>
              <div className="flex flex-col gap-3 p-md">
                <p className="font-body-sm text-body-sm text-slate">
                  Pour confirmer qu'il s'agit bien de la même société, consulte
                  la fiche officielle sur <strong>DirectInfo.ma</strong> (registre du
                  commerce, ICE, RC, adresse). Le nom de l'entreprise sera copié
                  automatiquement dans le presse-papier.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    const nom = alerte.nom_detecte || alerte.nom_tier || ''
                    if (nom) {
                      navigator.clipboard.writeText(nom).catch(() => {
                        /* fallback silencieux si clipboard indisponible */
                      })
                    }
                    window.open(
                      'https://www.directinfo.ma/recherche-multi-criteres',
                      '_blank',
                      'noopener,noreferrer',
                    )
                  }}
                  className="inline-flex items-center justify-center gap-2 self-start border border-primary bg-primary px-md py-2 font-label-md text-label-md text-on-primary transition-colors hover:bg-primary-container hover:text-on-primary-container focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  <span className="material-symbols-outlined text-base">
                    open_in_new
                  </span>
                  Vérifier sur DirectInfo.ma
                </button>
              </div>
            </div>

            {/* Décision administrative */}
            <div className="border border-outline-variant bg-surface-container-lowest">
              <div className="border-b border-outline-variant bg-surface px-md py-sm">
                <h2 className="font-headline-md text-headline-md text-ink">
                  Décision administrative
                </h2>
              </div>
              {(
                <div className="flex flex-col gap-4 p-md">
                  <div className="flex flex-col gap-1">
                    <label
                      className="font-label-caps text-label-caps text-slate"
                      htmlFor="commentaire"
                    >
                      Notes d'analyse (optionnel)
                    </label>
                    <textarea
                      id="commentaire"
                      rows={3}
                      value={commentaire}
                      onChange={(e) => setCommentaire(e.target.value)}
                      placeholder="Saisir un commentaire sur la divergence de nom…"
                      className="w-full border border-outline-variant bg-limestone p-2 font-body-sm text-ink outline-none transition-shadow focus:border-ink focus:ring-1 focus:ring-ink"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Button
                      variant="outline"
                      icon="block"
                      disabled={saving}
                      onClick={() => setConfirmAction('ignoree')}
                    >
                      Ignorer
                    </Button>
                    <Button
                      variant="clay"
                      icon="check_circle"
                      disabled={saving}
                      onClick={() => setConfirmAction('traitee')}
                    >
                      Confirmer &amp; traiter
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Fenêtre de confirmation */}
      {confirmAction === 'traitee' && (
        <ConfirmDialog
          title="Confirmer le traitement"
          icon="check_circle"
          variant="clay"
          confirmLabel="Confirmer & traiter"
          loading={saving}
          onCancel={() => setConfirmAction(null)}
          onConfirm={() => appliquer('traitee')}
          message={
            <>
              L'alerte <strong>{alerte.nom_detecte}</strong> sera marquée comme{' '}
              <strong>traitée</strong>.
              {commentaire.trim() && (
                <span className="mt-2 block text-slate">Note : « {commentaire.trim()} »</span>
              )}
            </>
          }
        />
      )}
      {confirmAction === 'ignoree' && (
        <ConfirmDialog
          title="Ignorer l'alerte"
          icon="block"
          variant="danger"
          confirmLabel="Ignorer l'alerte"
          loading={saving}
          onCancel={() => setConfirmAction(null)}
          onConfirm={() => appliquer('ignoree')}
          message={
            <>
              L'alerte <strong>{alerte.nom_detecte}</strong> sera marquée comme{' '}
              <strong>ignorée</strong> (faux positif). Elle restera consultable dans
              l'historique.
              {commentaire.trim() && (
                <span className="mt-2 block text-slate">Note : « {commentaire.trim()} »</span>
              )}
            </>
          }
        />
      )}
    </div>
  )
}
