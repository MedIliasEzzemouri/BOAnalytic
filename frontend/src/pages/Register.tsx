import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { errorMessage } from '../api/client'
import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }
    if (password.length < 8) {
      setError('Le mot de passe doit faire au moins 8 caractères.')
      return
    }
    setLoading(true)
    try {
      await register(nom, email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(errorMessage(err, "Échec de l'inscription."))
    } finally {
      setLoading(false)
    }
  }

  const field =
    'block w-full rounded border border-outline-variant bg-surface-container-lowest py-2.5 pl-10 pr-3 font-body-md text-ink outline-none transition-shadow placeholder:text-outline focus:border-primary focus:ring-2 focus:ring-primary'

  return (
    <AuthLayout>
      <div className="mb-8">
        <h1 className="mb-2 font-headline-lg text-headline-lg text-ink">Créer un compte</h1>
        <p className="font-body-md text-body-md text-slate">
          Rejoignez la veille juridique de Plastima Casablanca.
        </p>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label
            className="block font-caption text-[11px] font-semibold uppercase tracking-wider text-slate"
            htmlFor="nom"
          >
            Nom complet
          </label>
          <div className="relative">
            <Icon
              name="person"
              className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-[20px] text-slate"
            />
            <input
              id="nom"
              type="text"
              required
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="Jean Dupont"
              className={field}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label
            className="block font-caption text-[11px] font-semibold uppercase tracking-wider text-slate"
            htmlFor="email"
          >
            Adresse email
          </label>
          <div className="relative">
            <Icon
              name="mail"
              className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-[20px] text-slate"
            />
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nom@plastima.ma"
              className={field}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label
            className="block font-caption text-[11px] font-semibold uppercase tracking-wider text-slate"
            htmlFor="password"
          >
            Mot de passe
          </label>
          <div className="relative">
            <Icon
              name="lock"
              className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-[20px] text-slate"
            />
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className={`${field} tracking-widest`}
            />
          </div>
          <p className="font-caption text-caption text-outline">Minimum 8 caractères</p>
        </div>

        <div className="space-y-2">
          <label
            className="block font-caption text-[11px] font-semibold uppercase tracking-wider text-slate"
            htmlFor="confirm"
          >
            Confirmer le mot de passe
          </label>
          <div className="relative">
            <Icon
              name="lock_reset"
              className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-[20px] text-slate"
            />
            <input
              id="confirm"
              type="password"
              required
              minLength={8}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              className={`${field} tracking-widest`}
            />
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded border border-error/20 bg-error-container p-3 text-on-error-container"
          >
            <Icon name="error" className="mt-[2px] text-[18px]" />
            <span className="font-body-md text-body-md">{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded bg-primary px-4 py-3 font-body-md font-semibold text-on-primary transition-colors hover:bg-surface-tint focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-70"
        >
          {loading && <Icon name="progress_activity" className="animate-spin text-[20px]" />}
          {loading ? 'Création…' : "S'inscrire"}
        </button>
      </form>

      <div className="mt-5 flex items-start gap-3 rounded border border-outline-variant bg-surface-container-low/80 p-3">
        <Icon name="info" className="mt-0.5 shrink-0 text-[20px] text-outline" />
        <p className="font-caption text-caption text-slate">
          Tous les nouveaux comptes sont créés en rôle <strong>opérateur</strong>. Pour obtenir
          plus de droits, demandez à un administrateur existant.
        </p>
      </div>

      <div className="mt-6 font-body-md text-[15px]">
        <Link to="/login" className="flex items-center gap-1 text-primary hover:underline">
          <Icon name="arrow_back" className="text-[16px]" />
          Déjà un compte ? Se connecter
        </Link>
      </div>
    </AuthLayout>
  )
}
