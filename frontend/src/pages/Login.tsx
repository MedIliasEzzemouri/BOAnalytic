import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { errorMessage } from '../api/client'
import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Identifiants incorrects. Veuillez réessayer.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout>
      <div className="mb-8">
        <h1 className="mb-2 text-[32px] font-bold" style={{ color: '#0b1a2e' }}>Connexion</h1>
        <p className="text-[15px]" style={{ color: '#64748b' }}>
          Connectez-vous à votre espace BOAnalytic.
        </p>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <label
            className="block text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: '#64748b' }}
            htmlFor="email"
          >
            Email
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
              placeholder="exemple@plastima.ma"
              className="w-full rounded-lg border bg-white py-3 pl-10 pr-4 text-[15px] outline-none transition-shadow placeholder:text-gray-300 focus:ring-2"
              style={{ borderColor: '#e2e8f0', color: '#0b1a2e' }}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label
            className="block text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: '#64748b' }}
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border bg-white py-3 pl-10 pr-4 text-[15px] tracking-widest outline-none transition-shadow focus:ring-2"
              style={{ borderColor: '#e2e8f0', color: '#0b1a2e' }}
            />
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-red-100 bg-red-50 p-3 text-red-700"
          >
            <Icon name="error" className="mt-[2px] text-[18px]" />
            <span className="text-[14px]">{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg py-3 text-[15px] font-semibold text-white transition-colors disabled:opacity-70"
          style={{ background: '#3b82f6' }}
        >
          {loading && <Icon name="progress_activity" className="animate-spin text-[20px]" />}
          {loading ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>

      <div className="mt-6 flex items-start gap-2 rounded-lg border border-gray-200 bg-white p-3">
        <Icon name="info" className="mt-[2px] shrink-0 text-[18px] text-gray-400" />
        <p className="text-[13px] text-gray-500">
          Les comptes sont créés par l'administrateur. Contactez votre responsable pour accéder à la plateforme.
        </p>
      </div>
    </AuthLayout>
  )
}
