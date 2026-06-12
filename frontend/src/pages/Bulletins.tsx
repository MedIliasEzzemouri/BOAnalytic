import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { bulletinsApi, errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { Bulletin, BulletinStatut } from '../types'
import { ErrorBox, EmptyState } from '../components/ui'
import { TableSkeleton } from '../components/Skeleton'
import { StatutBulletinBadge } from '../components/badges'
import { formatDate } from '../lib/format'
import PageHeader from '../components/PageHeader'
import Button from '../components/Button'
import Modal from '../components/Modal'
import Icon from '../components/Icon'

const fieldCls =
  'w-full rounded border border-outline-variant bg-limestone p-2.5 font-body-md text-ink outline-none transition-colors focus:border-primary'

/** Extract BO number from filename like BOAL_5921.pdf or BO_5921_Ar.pdf */
function extraireNumeroFichier(name: string): string {
  const m = name.match(/[_-](\d{4,5})[_.-]/i) ?? name.match(/(\d{4,5})/)
  return m ? m[1] : ''
}

function ImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [option, setOption] = useState<1 | 2>(1)
  // Option 1 fields
  const [numero, setNumero] = useState('')
  const [annee, setAnnee] = useState(String(new Date().getFullYear()))
  // Option 2 fields
  const [file, setFile] = useState<File | null>(null)
  const [fileNumero, setFileNumero] = useState('')   // auto-extracted, editable
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function switchOption(o: 1 | 2) {
    setOption(o)
    setError(null)
    setSuccess(null)
  }

  function handleFileChange(f: File | null) {
    setFile(f)
    if (f) {
      const extracted = extraireNumeroFichier(f.name)
      setFileNumero(extracted)
    } else {
      setFileNumero('')
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setLoading(true)
    try {
      if (option === 1) {
        // Option 1 : numéro + année → téléchargement auto
        const num = parseInt(numero, 10)
        if (!num || num < 1000) { setError('Numéro invalide (ex: 5921 ou 7296)'); setLoading(false); return }
        const an = parseInt(annee, 10) || undefined
        const b = await bulletinsApi.downloadNumero(num, an)
        setSuccess(`Bulletin #${b.numero} téléchargé — pipeline ML en cours…`)
        setTimeout(() => onDone(), 2000)
      } else {
        // Option 2 : PDF seulement
        if (!file) { setError('Veuillez sélectionner un fichier PDF.'); setLoading(false); return }
        const num = parseInt(fileNumero, 10)
        if (!num || num < 1000) { setError('Numéro non détecté — renommez le fichier ex: BOAL_5921.pdf'); setLoading(false); return }
        const form = new FormData()
        form.append('file', file)
        form.append('numero', String(num))
        form.append('date_publication', `${new Date().getFullYear()}-01-01`)
        await bulletinsApi.upload(form)
        onDone()
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Nouveau bulletin" onClose={onClose} size="max-w-lg">
      <div className="p-md">
        {/* Option toggle */}
        <div className="mb-5 grid grid-cols-2 gap-2">
          {([1, 2] as const).map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => switchOption(o)}
              className={`flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-colors ${
                option === o ? 'border-primary bg-primary/5' : 'border-outline-variant hover:border-primary/40'
              }`}
            >
              <Icon
                name={o === 1 ? 'download' : 'upload_file'}
                className={`text-[28px] ${option === o ? 'text-primary' : 'text-slate'}`}
              />
              <span className={`font-label-md text-[13px] font-semibold ${option === o ? 'text-primary' : 'text-ink'}`}>
                Option {o}
              </span>
              <span className="font-body-sm text-[12px] text-slate text-center">
                {o === 1 ? "J'ai le numéro — téléchargement auto depuis sgg.gov.ma" : "J'ai le fichier PDF — import manuel"}
              </span>
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {option === 1 ? (
            <>
              <div>
                <label htmlFor="imp-numero" className="mb-1 block font-label-caps text-label-caps text-slate">Numéro du BO</label>
                <input
                  id="imp-numero" required type="number" min="1000"
                  value={numero} onChange={(e) => setNumero(e.target.value)}
                  placeholder="ex: 5921 ou 7296"
                  className={fieldCls} autoFocus
                />
              </div>
              <div>
                <label htmlFor="imp-annee" className="mb-1 block font-label-caps text-label-caps text-slate">Année de publication</label>
                <input
                  id="imp-annee" required type="number" min="2000" max="2099"
                  value={annee} onChange={(e) => setAnnee(e.target.value)}
                  placeholder="2026" className={fieldCls}
                />
              </div>
            </>
          ) : (
            <div>
              <label htmlFor="imp-file" className="mb-1 block font-label-caps text-label-caps text-slate">Fichier PDF</label>
              <input
                id="imp-file" required type="file" accept="application/pdf"
                onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                className="w-full rounded border border-outline-variant bg-limestone p-2 font-body-sm text-ink file:mr-3 file:rounded file:border-0 file:bg-primary file:px-3 file:py-1.5 file:font-label-md file:uppercase file:text-on-primary"
              />
              {file && (
                <p className="mt-1 font-body-sm text-[12px] text-slate">
                  {fileNumero
                    ? `Numéro détecté : ${fileNumero}`
                    : <span className="text-red-500">Numéro non détecté — renommez en BOAL_XXXX.pdf</span>}
                </p>
              )}
            </div>
          )}

          {error && <ErrorBox message={error} />}
          {success && (
            <div className="flex items-center gap-2 rounded border border-green-200 bg-green-50 px-4 py-3 font-body-md text-green-700">
              <Icon name="check_circle" className="text-[18px]" />
              {success}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={loading} icon={option === 1 ? 'download' : 'upload'}>
              {loading
                ? (option === 1 ? 'Téléchargement…' : 'Import…')
                : (option === 1 ? 'Télécharger' : 'Importer')}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  )
}

export default function Bulletins() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const [bulletins, setBulletins] = useState<Bulletin[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statut, setStatut] = useState<BulletinStatut | 'tous'>('tous')
  const [search, setSearch] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [busy, setBusy] = useState<number | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string | null>(null)

  function load() {
    setLoading(true)
    bulletinsApi.list()
      .then(setBulletins)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return bulletins.filter((b) => {
      if (statut !== 'tous' && b.statut !== statut) return false
      if (q && !b.numero.toLowerCase().includes(q)) return false
      return true
    })
  }, [bulletins, statut, search])

  // KPI counts
  const total = bulletins.length
  const traites = bulletins.filter((b) => b.statut === 'traite').length
  const enCours = bulletins.filter((b) => b.statut === 'en_cours').length
  const nonTraites = bulletins.filter((b) => b.statut === 'en_attente' || b.statut === 'erreur').length

  async function handleRetraiter(id: number) {
    setBusy(id)
    try {
      const updated = await bulletinsApi.retraiter(id)
      setBulletins((list) => list.map((b) => (b.id === id ? updated : b)))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleSync() {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const res = await bulletinsApi.syncUploads()
      setSyncMsg(res.message)
      if (res.imported > 0) load()
    } catch (err) {
      setSyncMsg(errorMessage(err))
    } finally {
      setSyncing(false)
    }
  }

  async function handleDelete(id: number, numero: string) {
    if (!confirm(`Supprimer définitivement le bulletin n°${numero} ?`)) return
    setBusy(id)
    try {
      await bulletinsApi.remove(id)
      setBulletins((list) => list.filter((b) => b.id !== id))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  function reset() {
    setSearch('')
    setStatut('tous')
  }

  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto w-full max-w-container-max">
        <PageHeader
          title="Bulletins Officiels"
          subtitle="Gérez et consultez tous vos bulletins officiels."
          actions={
            <>
              <a
                href="https://www.sgg.gov.ma/arabe/imprimerieofficielle.aspx"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded border border-outline-variant px-5 font-label-md uppercase tracking-wider text-ink transition-colors duration-200 hover:bg-surface-container-high"
              >
                <Icon name="open_in_new" className="text-[18px]" />
                Source officielle
              </a>
              {isAdmin && (
                <>
                  <Button
                    variant="outline"
                    icon="sync"
                    loading={syncing}
                    onClick={handleSync}
                  >
                    {syncing ? 'Synchronisation…' : 'Sync uploads'}
                  </Button>
                  <Button variant="clay" icon="add" onClick={() => setShowImport(true)}>
                    Nouveau bulletin
                  </Button>
                </>
              )}
            </>
          }
        />

        {syncMsg && (
          <div className="mb-4 flex items-center gap-2 rounded border border-outline-variant bg-surface-container px-4 py-3 font-body-md text-ink">
            <Icon name="info" className="text-[18px] text-primary" />
            {syncMsg}
            <button type="button" onClick={() => setSyncMsg(null)} className="ml-auto text-slate hover:text-ink">
              <Icon name="close" className="text-[16px]" />
            </button>
          </div>
        )}

        {/* Search + Filter + Reset */}
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-outline-variant bg-surface-container-lowest p-4 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">
              Rechercher
            </label>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Numéro de BO…"
                className="w-full rounded border border-outline-variant bg-white py-2.5 pl-10 pr-4 font-body-md text-ink outline-none transition-colors placeholder:text-slate/60 focus:border-primary"
              />
            </div>
          </div>
          <div className="w-full sm:w-52">
            <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">
              Filtrer par statut
            </label>
            <select
              value={statut}
              onChange={(e) => setStatut(e.target.value as BulletinStatut | 'tous')}
              className="w-full rounded border border-outline-variant bg-white py-2.5 px-3 font-body-md text-ink outline-none transition-colors focus:border-primary"
            >
              <option value="tous">Tous les statuts</option>
              <option value="traite">Traité</option>
              <option value="en_cours">En cours</option>
              <option value="en_attente">En attente</option>
              <option value="erreur">Erreur</option>
            </select>
          </div>
          <button
            type="button"
            onClick={reset}
            className="flex min-h-[44px] items-center gap-2 rounded border border-outline-variant px-4 font-label-md text-slate transition-colors hover:bg-limestone hover:text-ink"
          >
            <Icon name="refresh" className="text-[18px]" />
            Réinitialiser
          </button>
        </div>

        {/* KPI Cards */}
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KpiCard
            icon="description"
            label="Total Bulletins"
            value={total}
            pct={100}
            color="bg-blue-100"
            iconColor="text-blue-600"
            barColor="bg-blue-500"
          />
          <KpiCard
            icon="check_circle"
            label="Traités"
            value={traites}
            pct={total ? Math.round((traites / total) * 100) : 0}
            color="bg-green-100"
            iconColor="text-green-600"
            barColor="bg-green-500"
          />
          <KpiCard
            icon="schedule"
            label="En cours"
            value={enCours}
            pct={total ? Math.round((enCours / total) * 100) : 0}
            color="bg-amber-100"
            iconColor="text-amber-600"
            barColor="bg-amber-400"
          />
          <KpiCard
            icon="hourglass_empty"
            label="Non traités"
            value={nonTraites}
            pct={total ? Math.round((nonTraites / total) * 100) : 0}
            color="bg-slate-100"
            iconColor="text-slate-500"
            barColor="bg-slate-400"
          />
        </div>

        {error && <div className="mb-4"><ErrorBox message={error} /></div>}

        {/* Table */}
        <div className="rounded-lg border border-outline-variant bg-surface-container-lowest">
          <div className="flex items-center justify-between border-b border-outline-variant px-5 py-3">
            <span className="font-label-md font-semibold text-ink">
              <Icon name="grid_on" className="mr-2 inline text-[18px] text-slate" />
              Liste des Bulletins ({filtered.length})
            </span>
            <span className="font-body-sm text-slate">
              Affichage 1 – {filtered.length}
            </span>
          </div>

          {loading ? (
            <TableSkeleton rows={4} cols={6} />
          ) : filtered.length === 0 ? (
            <EmptyState icon="description" title="Aucun bulletin" hint="Aucun bulletin ne correspond à ces critères." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] border-collapse text-left">
                <caption className="sr-only">Liste des bulletins officiels</caption>
                <thead>
                  <tr className="border-b border-outline-variant bg-surface-container-low font-label-md text-[11px] uppercase tracking-wider text-secondary">
                    <th className="px-5 py-3"># ID</th>
                    <th className="px-5 py-3">Numéro</th>
                    <th className="px-5 py-3">Téléchargé</th>
                    <th className="px-5 py-3">Publié</th>
                    <th className="px-5 py-3">Statut</th>
                    <th className="px-5 py-3">Actions</th>
                    <th className="px-5 py-3 text-right">PDF</th>
                  </tr>
                </thead>
                <tbody className="font-body-md text-on-surface">
                  {filtered.map((b) => (
                    <tr
                      key={b.id}
                      className="border-b border-outline-variant last:border-0 hover:bg-surface-variant/20"
                    >
                      <td className="px-5 py-4">
                        <span className="font-semibold text-primary">#{b.id}</span>
                      </td>
                      <td className="px-5 py-4 font-bold text-ink">{b.numero}</td>
                      <td className="px-5 py-4 text-slate">{formatDate(b.created_at)}</td>
                      <td className="px-5 py-4 text-slate">{formatDate(b.date_publication)}</td>
                      <td className="px-5 py-4">
                        <StatutBulletinBadge statut={b.statut} />
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => navigate(`/bulletins/${b.id}`)}
                            className="flex items-center gap-1.5 rounded-full border border-primary px-3 py-1.5 font-label-md text-[12px] text-primary transition-colors hover:bg-primary/5"
                          >
                            <Icon name="visibility" className="text-[14px]" />
                            Voir annonces
                          </button>
                          {isAdmin && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleRetraiter(b.id)}
                                disabled={busy === b.id}
                                aria-label={`Retraiter le bulletin n°${b.numero}`}
                                className="flex h-8 w-8 items-center justify-center rounded text-primary transition-colors hover:bg-primary/10 disabled:opacity-40"
                              >
                                <Icon name="refresh" className={`text-[18px] ${busy === b.id ? 'animate-spin' : ''}`} />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDelete(b.id, b.numero)}
                                disabled={busy === b.id}
                                aria-label={`Supprimer le bulletin n°${b.numero}`}
                                className="flex h-8 w-8 items-center justify-center rounded text-secondary transition-colors hover:bg-error-container hover:text-error disabled:opacity-40"
                              >
                                <Icon name="delete" className="text-[18px]" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <span className="font-body-sm text-slate">
                          {b.nb_pages > 0 ? `${b.nb_pages} p.` : (
                            <span className="flex items-center justify-end gap-1 text-slate/60">
                              <Icon name="cancel" className="text-[14px]" />
                              Indisponible
                            </span>
                          )}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showImport && (
        <ImportModal
          onClose={() => setShowImport(false)}
          onDone={() => { setShowImport(false); load() }}
        />
      )}
    </div>
  )
}

function KpiCard({
  icon, label, value, pct, color, iconColor, barColor,
}: {
  icon: string; label: string; value: number
  pct: number; color: string; iconColor: string; barColor: string
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-outline-variant bg-surface-container-lowest p-4">
      <div className="flex items-start justify-between">
        <div className={`flex h-12 w-12 items-center justify-center rounded-full ${color}`}>
          <Icon name={icon} className={`text-[26px] ${iconColor}`} />
        </div>
        <div className="text-right">
          <p className="font-headline-lg text-[28px] font-bold leading-none text-ink">{value}</p>
          <p className="mt-0.5 font-body-sm text-slate">{pct}%</p>
        </div>
      </div>
      <div>
        <p className="mb-1.5 font-label-md text-[13px] text-secondary">{label}</p>
        <div className="h-1 w-full rounded-full bg-outline-variant/40">
          <div className={`h-1 rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  )
}
