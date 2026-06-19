import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { authApi, errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { User, Role } from '../types'
import { ErrorBox, EmptyState } from '../components/ui'
import { CardGridSkeleton } from '../components/Skeleton'
import PageHeader from '../components/PageHeader'
import Modal from '../components/Modal'
import Button from '../components/Button'
import Icon from '../components/Icon'

const fieldCls =
  'w-full rounded border border-outline-variant bg-limestone p-2.5 font-body-md text-ink outline-none transition-colors focus:border-primary'

function initials(nom: string): string {
  return nom
    .split(/\s+/)
    .map((p) => p[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

const ROLES: Array<{ value: string; label: string }> = [
  { value: 'admin', label: 'Administrateur' },
  { value: 'responsable', label: 'Responsable opérationnel' },
  { value: 'operateur', label: 'Opérateur' },
]

function roleLabel(r: string) {
  return ROLES.find((x) => x.value === r)?.label ?? r
}

// Couleur du badge par rôle.
const ROLE_BADGE: Record<string, { background: string; color: string }> = {
  admin: { background: '#dbeafe', color: '#1d4ed8' },
  responsable: { background: '#dcfce7', color: '#15803d' },
  operateur: { background: '#f1f5f9', color: '#475569' },
}

function roleBadgeStyle(r: string) {
  return ROLE_BADGE[r] ?? ROLE_BADGE.operateur
}

// ── Modal création ──────────────────────────────────────────────
function CreateUserModal({ onClose, onDone }: { onClose: () => void; onDone: (u: User) => void }) {
  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('operateur')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const u = await authApi.createUser(nom.trim(), email.trim(), password, role)
      onDone(u)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Nouvel utilisateur" onClose={onClose}>
      <form className="flex flex-col gap-4 p-md" onSubmit={handleSubmit}>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">Nom complet</label>
          <input required value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex: Ahmed Benali" className={fieldCls} autoFocus />
        </div>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">Email</label>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ahmed@plastima.ma" className={fieldCls} />
        </div>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">Mot de passe</label>
          <input required type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="8 caractères minimum" className={fieldCls} />
        </div>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">Rôle</label>
          <select value={role} onChange={(e) => setRole(e.target.value)} className={fieldCls}>
            {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        {error && <ErrorBox message={error} />}
        <div className="flex justify-end gap-3 pt-1">
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" loading={loading} icon="person_add">
            {loading ? 'Création…' : 'Créer'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Modal édition ───────────────────────────────────────────────
function EditUserModal({ user, onClose, onDone }: { user: User; onClose: () => void; onDone: (u: User) => void }) {
  const [nom, setNom] = useState(user.nom)
  const [email, setEmail] = useState(user.email)
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const data: { nom?: string; email?: string; password?: string } = {}
    if (nom.trim() !== user.nom) data.nom = nom.trim()
    if (email.trim() !== user.email) data.email = email.trim()
    if (password) data.password = password
    if (Object.keys(data).length === 0) { onClose(); return }
    setLoading(true)
    try {
      const u = await authApi.updateUser(user.id, data)
      onDone(u)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Modifier — ${user.nom}`} onClose={onClose}>
      <form className="flex flex-col gap-4 p-md" onSubmit={handleSubmit}>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">Nom complet</label>
          <input required value={nom} onChange={(e) => setNom(e.target.value)} className={fieldCls} autoFocus />
        </div>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">Email</label>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={fieldCls} />
        </div>
        <div>
          <label className="mb-1 block font-label-caps text-[11px] uppercase tracking-wider text-slate">
            Nouveau mot de passe <span className="font-normal normal-case text-slate/60">(laisser vide = inchangé)</span>
          </label>
          <input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="8 caractères minimum" className={fieldCls} />
        </div>
        {error && <ErrorBox message={error} />}
        <div className="flex justify-end gap-3 pt-1">
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" loading={loading} icon="save">
            {loading ? 'Sauvegarde…' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Composant principal ─────────────────────────────────────────
export default function Utilisateurs() {
  const { user: current, isAdmin } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('tous')
  const [busy, setBusy] = useState<number | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)

  function load() {
    setLoading(true)
    authApi
      .listUsers()
      .then(setUsers)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return users.filter((u) => {
      if (roleFilter !== 'tous' && u.role !== roleFilter) return false
      if (q && !u.nom.toLowerCase().includes(q) && !u.email.toLowerCase().includes(q))
        return false
      return true
    })
  }, [users, search, roleFilter])

  async function changeRole(u: User, next: string) {
    if (next === u.role) return
    setBusy(u.id)
    try {
      await authApi.setRole(u.id, next)
      setUsers((list) => list.map((x) => (x.id === u.id ? { ...x, role: next as Role } : x)))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function toggleActif(u: User) {
    setBusy(u.id)
    try {
      await authApi.setActif(u.id, !u.actif)
      setUsers((list) => list.map((x) => (x.id === u.id ? { ...x, actif: !x.actif } : x)))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function deleteUser(u: User) {
    if (!confirm(`Supprimer définitivement l'utilisateur "${u.nom}" (${u.email}) ?`)) return
    setBusy(u.id)
    try {
      await authApi.deleteUser(u.id)
      setUsers((list) => list.filter((x) => x.id !== u.id))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto w-full max-w-container-max">
        <PageHeader
          title="Gestion des Utilisateurs"
          subtitle="Gérez les accès, rôles et privilèges administratifs."
          actions={
            isAdmin ? (
              <Button icon="person_add" variant="clay" onClick={() => setShowCreate(true)}>
                Nouvel utilisateur
              </Button>
            ) : undefined
          }
        />

        {/* Toolbar */}
        <div className="mb-6 flex flex-col items-stretch justify-between gap-4 rounded-lg border border-outline-variant bg-surface-container-lowest px-6 py-4 sm:flex-row sm:items-center">
          <div className="relative w-full sm:w-72">
            <label htmlFor="rech-user" className="sr-only">Rechercher un utilisateur</label>
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-secondary" />
            <input
              id="rech-user"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher par nom ou email…"
              className="w-full rounded border border-outline-variant bg-limestone py-2 pl-9 pr-4 font-body-md text-ink outline-none transition-colors focus:border-primary"
            />
          </div>
          <div>
            <label htmlFor="filtre-role" className="sr-only">Filtrer par rôle</label>
            <select
              id="filtre-role"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded border border-outline-variant bg-limestone px-4 py-2 font-label-md text-label-md text-ink outline-none focus:border-primary"
            >
              <option value="tous">Tous les rôles</option>
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
        </div>

        {error && <div className="mb-6"><ErrorBox message={error} /></div>}

        {loading ? (
          <CardGridSkeleton count={6} />
        ) : filtered.length === 0 ? (
          <div className="rounded-lg border border-outline-variant bg-surface-container-lowest">
            <EmptyState icon="person_off" title="Aucun utilisateur" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((u) => {
              const isSelf = current?.user_id === u.id
              return (
                <article
                  key={u.id}
                  className="flex flex-col rounded-lg border border-outline-variant bg-surface-container-lowest p-6 transition-colors hover:border-outline"
                >
                  <div className="mb-4 flex items-start justify-between">
                    <div className="flex items-center gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-inverse-surface font-bold text-inverse-on-surface" aria-hidden="true">
                        {initials(u.nom)}
                      </div>
                      <div className="min-w-0">
                        <h2 className="truncate font-headline-md text-body-lg font-bold text-ink">{u.nom}</h2>
                        <p className="truncate font-body-md text-caption text-slate">{u.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {isSelf && (
                        <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-600">VOUS</span>
                      )}
                      {isAdmin && !isSelf && (
                        <button
                          type="button"
                          onClick={() => setEditUser(u)}
                          disabled={busy === u.id}
                          title="Modifier"
                          className="flex h-8 w-8 items-center justify-center rounded border border-outline-variant text-slate hover:border-primary hover:text-primary disabled:opacity-40"
                        >
                          <Icon name="edit" className="text-[16px]" />
                        </button>
                      )}
                      {isAdmin && !isSelf && (
                        <button
                          type="button"
                          onClick={() => deleteUser(u)}
                          disabled={busy === u.id}
                          title="Supprimer"
                          className="flex h-8 w-8 items-center justify-center rounded border border-outline-variant text-slate hover:border-red-400 hover:text-red-500 disabled:opacity-40"
                        >
                          <Icon name="delete" className="text-[16px]" />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 border-b border-outline-variant pb-4">
                    <span
                      className="rounded px-2 py-0.5 text-[10px] font-bold uppercase"
                      style={roleBadgeStyle(u.role)}
                    >
                      {roleLabel(u.role)}
                    </span>
                    <span className={`flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase ${u.actif ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {u.actif && <span className="h-2 w-2 rounded-full bg-green-500" aria-hidden="true" />}
                      {u.actif ? 'Actif' : 'Désactivé'}
                    </span>
                  </div>

                  {/* Actions — admin only */}
                  {isAdmin ? (
                    <div className="mt-auto flex items-center justify-between gap-2 pt-4">
                      <select
                        value={u.role}
                        onChange={(e) => changeRole(u, e.target.value)}
                        disabled={isSelf || busy === u.id}
                        className="rounded border border-outline-variant bg-limestone px-3 py-1.5 text-[13px] text-ink outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                      <button
                        type="button"
                        onClick={() => toggleActif(u)}
                        disabled={isSelf || busy === u.id}
                        className={`text-[13px] font-semibold uppercase tracking-tight transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${u.actif ? 'text-red-500 hover:text-red-700' : 'text-green-600 hover:text-green-800'}`}
                      >
                        {u.actif ? 'Désactiver' : 'Réactiver'}
                      </button>
                    </div>
                  ) : (
                    <div className="mt-auto pt-4">
                      <span className="font-body-sm text-[12px] italic text-slate">Lecture seule</span>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </div>

      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onDone={(u) => { setUsers((list) => [u as unknown as User, ...list]); setShowCreate(false) }}
        />
      )}

      {editUser && (
        <EditUserModal
          user={editUser}
          onClose={() => setEditUser(null)}
          onDone={(u) => { setUsers((list) => list.map((x) => (x.id === u.id ? u as unknown as User : x))); setEditUser(null) }}
        />
      )}
    </div>
  )
}
