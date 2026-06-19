// Types TypeScript LegalEye — alignés sur les schémas Pydantic du backend.

// Aligné sur les rôles backend (colonne user.role).
export type Role = 'admin' | 'responsable' | 'operateur'

export interface User {
  id: number
  nom: string
  email: string
  role: Role
  actif: boolean
  created_at: string
}

export interface AuthUser {
  user_id: number
  nom: string
  role: Role
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: number
  nom: string
  role: Role
}

export interface Tier {
  id: number
  nom: string
  nom_normalise: string
  type_tier: 'client' | 'fournisseur'
  secteur: string | null
  ville: string | null
  rc_numero: string | null
  actif: boolean
  created_at: string
}

export interface TierCreate {
  nom: string
  type_tier: string
  secteur?: string | null
  ville?: string | null
  rc_numero?: string | null
}

export type BulletinStatut = 'en_attente' | 'en_cours' | 'traite' | 'erreur'

export interface Bulletin {
  id: number
  numero: string
  date_publication: string
  nb_pages: number
  nb_annonces_legales: number
  nb_annonces_judiciaires: number
  source: 'scraping' | 'manuel'
  statut: BulletinStatut
  message_erreur: string | null
  created_at: string
}

export interface ArticleEntreprise {
  id: number
  bulletin_id: number
  nom_entreprise: string | null
  texte_annonce: string
  type_annonce: 'creation' | 'modification' | 'cession' | 'liquidation' | null
  score_classification: number | null
  score_ner: number | null
  source_nom: string | null
  page_bulletin: number | null
  created_at: string
}

export interface ArticleMahakim {
  id: number
  bulletin_id: number
  nom_entreprise: string | null
  texte_annonce: string
  type_procedure: string | null
  score_ner: number | null
  tribunal: string | null
  page_bulletin: number | null
  created_at: string
}

export type AlerteStatut = 'nouvelle' | 'vue' | 'traitee' | 'ignoree'
export type AlertePriorite = 'haute' | 'moyenne' | 'basse'

export interface Alerte {
  id: number
  tier_id: number
  nom_detecte: string
  nom_tier: string
  score_similarite: number
  type_annonce: string | null
  statut: AlerteStatut
  priorite: AlertePriorite
  commentaire: string | null
  created_at: string
  traitee_at: string | null
  article_entreprise: ArticleEntreprise | null
  article_mahakim: ArticleMahakim | null
  tier: Tier | null
}

export interface Stats {
  total_bulletins: number
  total_annonces_legales: number
  total_annonces_judiciaires: number
  total_tiers: number
  total_alertes: number
  alertes_nouvelles: number
  par_type: Record<string, number>
  par_mois: Array<{ annee: number; mois: number; total: number }>
}

export interface PrioriteCount {
  priorite: string
  total: number
}

export interface TopTier {
  nom: string
  total: number
}
