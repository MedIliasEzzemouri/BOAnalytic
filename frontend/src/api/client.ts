import axios from 'axios'
import type {
  Alerte,
  ArticleEntreprise,
  ArticleMahakim,
  Bulletin,
  Stats,
  Tier,
  TierCreate,
  TokenResponse,
  User,
} from '../types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const TOKEN_KEY = 'legaleye_token'

export const api = axios.create({
  baseURL: API_URL,
})

// Injecte le JWT Bearer sur chaque requête.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 → on purge la session et on renvoie vers /login.
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('legaleye_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

/** Extrait un message d'erreur lisible depuis une erreur axios. */
export function errorMessage(err: unknown, fallback = 'Une erreur est survenue'): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
    return err.message || fallback
  }
  return fallback
}

// ── Auth ──
export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/api/auth/login', { email, password }).then((r) => r.data),
  register: (nom: string, email: string, password: string) =>
    api
      .post<TokenResponse>('/api/auth/register', { nom, email, password })
      .then((r) => r.data),
  me: () => api.get<User>('/api/auth/me').then((r) => r.data),
  listUsers: () => api.get<User[]>('/api/auth/users').then((r) => r.data),
  createUser: (nom: string, email: string, password: string, role: string) =>
    api.post<User>('/api/auth/users', { nom, email, password }, { params: { role } }).then((r) => r.data),
  updateUser: (userId: number, data: { nom?: string; email?: string; password?: string }) =>
    api.put<User>(`/api/auth/users/${userId}`, null, { params: data }).then((r) => r.data),
  deleteUser: (userId: number) =>
    api.delete(`/api/auth/users/${userId}`).then((r) => r.data),
  setRole: (userId: number, role: string) =>
    api.put(`/api/auth/users/${userId}/role`, null, { params: { role } }).then((r) => r.data),
  setActif: (userId: number, actif: boolean) =>
    api.put(`/api/auth/users/${userId}/actif`, null, { params: { actif } }).then((r) => r.data),
}

// ── Bulletins ──
export const bulletinsApi = {
  list: () => api.get<Bulletin[]>('/api/bulletins/').then((r) => r.data),
  get: (id: number) => api.get<Bulletin>(`/api/bulletins/${id}`).then((r) => r.data),
  upload: (form: FormData) =>
    api
      .post<Bulletin>('/api/bulletins/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data),
  retraiter: (id: number) =>
    api.post<Bulletin>(`/api/bulletins/${id}/retraiter`).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/bulletins/${id}`).then((r) => r.data),
  downloadNumero: (numero: number, annee?: number) => {
    const form = new FormData()
    form.append('numero', String(numero))
    if (annee) form.append('annee', String(annee))
    return api.post<Bulletin>('/api/bulletins/download-numero', form).then((r) => r.data)
  },
  syncUploads: () =>
    api
      .post<{ imported: number; skipped: number; bulletins_importes: string[]; message: string }>(
        '/api/bulletins/sync-uploads',
      )
      .then((r) => r.data),
  articles: (id: number, params?: { limit?: number; offset?: number }) =>
    api
      .get<{ legales: ArticleEntreprise[]; judiciaires: ArticleMahakim[] }>(
        `/api/bulletins/${id}/articles`,
        { params },
      )
      .then((r) => r.data),
}

// ── Tiers ──
export const tiersApi = {
  list: (params?: { type_tier?: string; actif?: boolean; search?: string }) =>
    api.get<Tier[]>('/api/tiers/', { params }).then((r) => r.data),
  get: (id: number) => api.get<Tier>(`/api/tiers/${id}`).then((r) => r.data),
  create: (data: TierCreate) => api.post<Tier>('/api/tiers/', data).then((r) => r.data),
  update: (id: number, data: Partial<TierCreate> & { actif?: boolean }) =>
    api.put<Tier>(`/api/tiers/${id}`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/tiers/${id}`).then((r) => r.data),
  importCsv: (form: FormData) =>
    api
      .post('/api/tiers/import-csv', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data),
}

// ── Alertes ──
export const alertesApi = {
  list: (params?: { statut?: string; priorite?: string; tier_id?: number; bulletin_id?: number }) =>
    api.get<Alerte[]>('/api/alertes/', { params }).then((r) => r.data),
  get: (id: number) => api.get<Alerte>(`/api/alertes/${id}`).then((r) => r.data),
  update: (id: number, data: { statut?: string; commentaire?: string }) =>
    api.put<Alerte>(`/api/alertes/${id}`, data).then((r) => r.data),
  marquerVue: (id: number) => api.post(`/api/alertes/${id}/vue`).then((r) => r.data),
  countNouvelles: () =>
    api.get<{ count: number }>('/api/alertes/count/nouvelles').then((r) => r.data.count),
}

// ── Stats ──
export const statsApi = {
  /** `jours` borne les KPI à une période (7/30/90…). Absent = depuis le début. */
  get: (jours?: number | null) =>
    api
      .get<Stats>('/api/stats/', { params: jours ? { jours } : undefined })
      .then((r) => r.data),
  parPriorite: () =>
    api.get<Record<string, number>>('/api/stats/alertes-par-priorite').then((r) => r.data),
  topTiers: (limit = 10) =>
    api
      .get<Array<{ nom: string; nb_alertes: number }>>('/api/stats/top-tiers', {
        params: { limit },
      })
      .then((r) => r.data),
}

// ── Exports ──
export const exportsApi = {
  /**
   * Télécharge le rapport PDF global et déclenche le téléchargement navigateur.
   * L'endpoint est protégé par JWT : on passe par axios (header Authorization)
   * puis on crée une URL d'objet locale.
   */
  rapportGlobal: async (jours: number): Promise<void> => {
    const res = await api.get('/api/exports/rapport-global', {
      params: { jours },
      responseType: 'blob',
    })
    const disposition = String(res.headers['content-disposition'] ?? '')
    const match = disposition.match(/filename="?([^"]+)"?/)
    const filename = match?.[1] ?? `LegalEye_rapport_${jours}j.pdf`
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

// ── Articles (screenshot annoté) ──
/**
 * Récupère la capture annotée du BO. L'endpoint est protégé par JWT :
 * une balise <img> ne peut pas envoyer le header Authorization, on télécharge
 * donc le PNG via axios puis on crée une URL d'objet locale.
 * L'appelant doit révoquer l'URL avec URL.revokeObjectURL().
 */
export async function fetchScreenshot(
  kind: 'entreprise' | 'mahakim',
  articleId: number,
): Promise<string> {
  const res = await api.get(`/api/articles/${kind}/${articleId}/screenshot`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(res.data as Blob)
}
