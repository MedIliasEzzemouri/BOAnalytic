import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { tiersApi, alertesApi, errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { Alerte, Tier, TierCreate } from '../types'
import { ErrorBox, EmptyState } from '../components/ui'
import { TableSkeleton } from '../components/Skeleton'
import { PrioriteBadge, StatutAlerteBadge } from '../components/badges'
import { formatDate, formatScore } from '../lib/format'
import PageHeader from '../components/PageHeader'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Icon from '../components/Icon'

const EMPTY: TierCreate = {
  nom: '',
  type_tier: 'client',
  secteur: '',
  ville: '',
  rc_numero: '',
}

const fieldCls =
  'w-full rounded border border-outline-variant bg-limestone p-2.5 font-body-md text-ink outline-none transition-colors focus:border-primary'

function TierModal({
  initial,
  onClose,
  onSaved,
}: {
  initial: Tier | null
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState<TierCreate>(
    initial
      ? {
          nom: initial.nom,
          type_tier: initial.type_tier,
          secteur: initial.secteur ?? '',
          ville: initial.ville ?? '',
          rc_numero: initial.rc_numero ?? '',
        }
      : EMPTY,
  )
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function set<K extends keyof TierCreate>(key: K, value: TierCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (initial) await tiersApi.update(initial.id, form)
      else await tiersApi.create(form)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={initial ? 'Modifier le tiers' : 'Nouveau tiers'} onClose={onClose}>
      <form className="flex flex-col gap-4 p-md" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="t-nom" className="mb-1 block font-label-caps text-label-caps text-slate">
            Nom de l'entité
          </label>
          <input
            id="t-nom"
            required
            value={form.nom}
            onChange={(e) => set('nom', e.target.value)}
            placeholder="Groupe OCP"
            className={fieldCls}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="t-type" className="mb-1 block font-label-caps text-label-caps text-slate">
              Type
            </label>
            <select
              id="t-type"
              value={form.type_tier}
              onChange={(e) => set('type_tier', e.target.value)}
              className={fieldCls}
            >
              <option value="client">Client</option>
              <option value="fournisseur">Fournisseur</option>
            </select>
          </div>
          <div>
            <label htmlFor="t-ville" className="mb-1 block font-label-caps text-label-caps text-slate">
              Ville
            </label>
            <input
              id="t-ville"
              value={form.ville ?? ''}
              onChange={(e) => set('ville', e.target.value)}
              placeholder="Casablanca"
              className={fieldCls}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="t-secteur" className="mb-1 block font-label-caps text-label-caps text-slate">
              Secteur
            </label>
            <input
              id="t-secteur"
              value={form.secteur ?? ''}
              onChange={(e) => set('secteur', e.target.value)}
              placeholder="Industrie"
              className={fieldCls}
            />
          </div>
          <div>
            <label htmlFor="t-rc" className="mb-1 block font-label-caps text-label-caps text-slate">
              N° RC
            </label>
            <input
              id="t-rc"
              value={form.rc_numero ?? ''}
              onChange={(e) => set('rc_numero', e.target.value)}
              placeholder="40327"
              className={fieldCls}
            />
          </div>
        </div>
        {error && <ErrorBox message={error} />}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" variant="clay" loading={loading}>
            {initial ? 'Enregistrer' : 'Créer'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function TierAlertesModal({ tier, onClose }: { tier: Tier; onClose: () => void }) {
  const navigate = useNavigate()
  const [alertes, setAlertes] = useState<Alerte[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    alertesApi
      .list({ tier_id: tier.id })
      .then(setAlertes)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [tier.id])

  return (
    <Modal title={`Alertes — ${tier.nom}`} onClose={onClose} size="max-w-2xl">
      <div className="flex max-h-[70vh] flex-col gap-3 overflow-y-auto p-md">
        {error && <ErrorBox message={error} />}
        {loading ? (
          <p className="font-body-md text-secondary">Chargement…</p>
        ) : alertes.length === 0 ? (
          <EmptyState
            icon="notifications_off"
            title="Aucune alerte"
            hint={`Aucune alerte n'a été générée pour « ${tier.nom} ».`}
          />
        ) : (
          alertes.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => navigate(`/alertes/${a.id}`)}
              className="flex w-full flex-col gap-2 rounded border border-outline-variant bg-surface p-4 text-left transition-colors hover:bg-surface-container-high"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-ink">{a.nom_detecte}</span>
                <div className="flex shrink-0 items-center gap-2">
                  <PrioriteBadge priorite={a.priorite} />
                  <StatutAlerteBadge statut={a.statut} />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-caption text-caption text-secondary">
                {a.type_annonce && <span className="capitalize">{a.type_annonce}</span>}
                <span>Similarité {formatScore(a.score_similarite)}</span>
                <span>{formatDate(a.created_at)}</span>
              </div>
            </button>
          ))
        )}
      </div>
    </Modal>
  )
}

export default function Tiers() {
  const { isAdmin } = useAuth()
  const [tiers, setTiers] = useState<Tier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<'tous' | 'client' | 'fournisseur'>('tous')
  const [modal, setModal] = useState<{ open: boolean; tier: Tier | null }>({
    open: false,
    tier: null,
  })
  const [alertesTier, setAlertesTier] = useState<Tier | null>(null)

  function load() {
    setLoading(true)
    const params: { type_tier?: string; search?: string } = {}
    if (typeFilter !== 'tous') params.type_tier = typeFilter
    if (search.trim()) params.search = search.trim()
    tiersApi
      .list(params)
      .then(setTiers)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    const t = setTimeout(load, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, typeFilter])

  async function handleDelete(tier: Tier) {
    if (!confirm(`Archiver le tiers « ${tier.nom} » ?`)) return
    try {
      await tiersApi.remove(tier.id)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto flex w-full max-w-container-max flex-col gap-6">
        <PageHeader
          title="Tiers"
          subtitle="Registre unifié des tiers soumis à la surveillance réglementaire."
          actions={
            isAdmin && (
              <Button
                variant="clay"
                icon="add"
                onClick={() => setModal({ open: true, tier: null })}
              >
                Nouveau tiers
              </Button>
            )
          }
        />

        {/* Filtres */}
        <div className="flex flex-col items-stretch justify-between gap-4 md:flex-row md:items-center">
          <div className="relative w-full md:w-96">
            <label htmlFor="rech-tier" className="sr-only">
              Rechercher un tiers
            </label>
            <Icon
              name="search"
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate"
            />
            <input
              id="rech-tier"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher un tiers…"
              className="w-full rounded border border-outline-variant bg-surface-container-lowest py-2.5 pl-11 pr-3 font-body-md text-ink outline-none transition-colors focus:border-primary"
            />
          </div>
          <div className="flex gap-2" role="group" aria-label="Filtrer par type">
            {(['tous', 'client', 'fournisseur'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTypeFilter(t)}
                aria-pressed={typeFilter === t}
                className={`min-h-[40px] rounded px-4 py-2 font-label-md text-label-md uppercase transition-colors duration-200 ${
                  typeFilter === t
                    ? 'bg-primary text-white'
                    : 'border border-outline-variant text-secondary hover:bg-surface-container-high'
                }`}
              >
                {t === 'tous' ? 'Tous' : t}
              </button>
            ))}
          </div>
        </div>

        {error && <ErrorBox message={error} />}

        {/* Table */}
        <section className="rounded-lg border border-outline-variant bg-surface-container-lowest">
          {loading ? (
            <TableSkeleton rows={6} cols={6} />
          ) : tiers.length === 0 ? (
            <EmptyState
              icon="groups"
              title="Aucun tiers"
              hint="Aucun partenaire ne correspond à cette recherche."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] border-collapse text-left">
                <caption className="sr-only">Liste des partenaires</caption>
                <thead>
                  <tr className="border-b border-outline-variant">
                    {["Nom de l'entité", 'Type', 'Secteur', 'Ville', 'N° RC', 'Statut', 'Actions'].map(
                      (h) => (
                        <th
                          key={h}
                          scope="col"
                          className="px-6 py-4 font-label-md text-label-md uppercase tracking-widest text-secondary last:text-right"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="font-body-md text-ink">
                  {tiers.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => setAlertesTier(t)}
                      className="cursor-pointer border-b border-outline-variant transition-colors last:border-0 hover:bg-surface"
                      title={`Voir les alertes de ${t.nom}`}
                    >
                      <td className="px-6 py-5 font-semibold">{t.nom}</td>
                      <td className="px-6 py-5 capitalize text-slate">{t.type_tier}</td>
                      <td className="px-6 py-5 text-slate">{t.secteur ?? '—'}</td>
                      <td className="px-6 py-5 text-slate">{t.ville ?? '—'}</td>
                      <td className="px-6 py-5 font-label-md text-sm text-slate">
                        {t.rc_numero ? `RC ${t.rc_numero}` : '—'}
                      </td>
                      <td className="px-6 py-5">
                        <span
                          className={`inline-flex items-center px-2 py-1 font-label-md text-[11px] uppercase tracking-widest ${
                            t.actif
                              ? 'border border-outline-variant text-slate'
                              : 'border border-outline-variant bg-surface-container text-outline'
                          }`}
                        >
                          {t.actif ? 'Actif' : 'Archivé'}
                        </span>
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex justify-end gap-1 text-slate">
                          {isAdmin ? (
                            <>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setModal({ open: true, tier: t })
                                }}
                                aria-label={`Modifier ${t.nom}`}
                                className="flex h-10 w-10 items-center justify-center rounded transition-colors hover:bg-surface-container-high hover:text-primary"
                              >
                                <Icon name="edit" className="text-[20px]" />
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleDelete(t)
                                }}
                                aria-label={`Archiver ${t.nom}`}
                                className="flex h-10 w-10 items-center justify-center rounded transition-colors hover:bg-error-container hover:text-error"
                              >
                                <Icon name="archive" className="text-[20px]" />
                              </button>
                            </>
                          ) : (
                            <span aria-hidden="true">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!loading && tiers.length > 0 && (
            <div className="border-t border-outline-variant px-6 py-4">
              <span className="font-caption text-caption text-secondary">
                {tiers.length} entité{tiers.length > 1 ? 's' : ''}
              </span>
            </div>
          )}
        </section>
      </div>

      {modal.open && (
        <TierModal
          initial={modal.tier}
          onClose={() => setModal({ open: false, tier: null })}
          onSaved={() => {
            setModal({ open: false, tier: null })
            load()
          }}
        />
      )}

      {alertesTier && (
        <TierAlertesModal tier={alertesTier} onClose={() => setAlertesTier(null)} />
      )}
    </div>
  )
}
