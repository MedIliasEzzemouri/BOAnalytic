import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi, TOKEN_KEY } from '../api/client'
import type { AuthUser } from '../types'

const USER_KEY = 'legaleye_user'

interface AuthContextValue {
  user: AuthUser | null
  isAuthenticated: boolean
  isAdmin: boolean
  /** admin + responsable : retraiter/supprimer bulletins, exporter rapports. */
  canManageBulletins: boolean
  /** admin + responsable : exporter les rapports PDF. */
  canExport: boolean
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (nom: string, email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function readStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(readStoredUser)
  const [loading, setLoading] = useState(true)

  // Au montage : si un token existe, on valide la session via /me.
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setLoading(false)
      return
    }
    authApi
      .me()
      .then((me) => {
        const u: AuthUser = { user_id: me.id, nom: me.nom, role: me.role }
        setUser(u)
        localStorage.setItem(USER_KEY, JSON.stringify(u))
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  function persist(token: string, u: AuthUser) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    setUser(u)
  }

  async function login(email: string, password: string) {
    const res = await authApi.login(email, password)
    persist(res.access_token, { user_id: res.user_id, nom: res.nom, role: res.role })
  }

  async function register(nom: string, email: string, password: string) {
    const res = await authApi.register(nom, email, password)
    persist(res.access_token, { user_id: res.user_id, nom: res.nom, role: res.role })
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isAdmin: user?.role === 'admin',
        canManageBulletins: user?.role === 'admin' || user?.role === 'responsable',
        canExport: user?.role === 'admin' || user?.role === 'responsable',
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé dans un AuthProvider')
  return ctx
}
