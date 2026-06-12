import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { alertesApi } from '../api/client'
import Icon from './Icon'

interface NavItem {
  to: string
  label: string
  icon: string
  adminOnly?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Tableau de bord', icon: 'dashboard' },
  { to: '/bulletins', label: 'Bulletins', icon: 'description' },
  { to: '/alertes', label: 'Alertes', icon: 'notifications_active' },
  { to: '/tiers', label: 'Partenaires', icon: 'groups' },
  { to: '/utilisateurs', label: 'Utilisateurs', icon: 'manage_accounts', adminOnly: true },
]

/** Coque applicative : SideNavBar + TopNavBar + zone de contenu. */
export default function Layout() {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [nouvelles, setNouvelles] = useState<number | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    alertesApi
      .countNouvelles()
      .then(setNouvelles)
      .catch(() => setNouvelles(null))
  }, [])

  // Ferme le menu mobile à chaque changement de route.
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const items = NAV.filter((i) => !i.adminOnly || isAdmin)

  return (
    <div className="flex h-screen overflow-hidden bg-background text-on-surface">
      <a href="#contenu-principal" className="skip-link">
        Aller au contenu principal
      </a>

      {/* SideNavBar */}
      <nav
        aria-label="Navigation principale"
        className={`fixed left-0 top-0 z-50 flex h-full w-64 flex-col px-3 py-5 transition-transform duration-200 md:translate-x-0 ${
          menuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ background: '#0b1a2e' }}
      >
        {/* PLASTIMA */}
        <div className="mb-5 px-3 pt-1">
          <img src="/plastima-logo.png" alt="Plastima" className="h-6 w-auto opacity-70" />
        </div>

        {/* Logo + subtitle */}
        <div className="mb-8 px-3">
          <div className="text-[26px] font-extrabold leading-none">
            <span style={{ color: '#f97316' }}>BO</span>
            <span className="text-white">Analytic</span>
          </div>
          <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: '#475569' }}>
            Veille Bulletin Officiel
          </p>
        </div>

        <ul className="flex-1 space-y-1">
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `group flex min-h-[44px] items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium transition-colors duration-150 ${
                    isActive
                      ? 'font-semibold'
                      : 'hover:bg-white/5'
                  }`
                }
                style={({ isActive }) => isActive
                  ? { background: 'rgba(249,115,22,0.12)', color: '#f97316' }
                  : { color: '#94a3b8' }
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon name={item.icon} fill={isActive} />
                    <span className="flex-1">{item.label}</span>
                    {item.to === '/alertes' && !!nouvelles && (
                      <span
                        className="rounded-full px-1.5 py-0.5 text-[10px] font-bold text-white"
                        style={{ background: '#f97316' }}
                        aria-label={`${nouvelles} nouvelles alertes`}
                      >
                        {nouvelles}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="mt-auto border-t pt-4" style={{ borderColor: '#1e3a5f' }}>
          <div className="flex items-center gap-3 px-3 py-2">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
              style={{ background: '#3b82f6' }}
              aria-hidden="true"
            >
              {(user?.nom ?? '?').split(/\s+/).map((p: string) => p[0] ?? '').join('').slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[14px] font-semibold text-white">{user?.nom}</p>
              <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#64748b' }}>
                {user?.role === 'admin' ? 'Administrateur' : user?.role}
              </p>
            </div>
          </div>
        </div>
      </nav>

      {/* Overlay mobile */}
      {menuOpen && (
        <div
          className="fixed inset-0 z-40 bg-ink/40 md:hidden"
          onClick={() => setMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Contenu */}
      <div className="flex h-full flex-1 flex-col md:ml-64">
        <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-outline-variant bg-surface px-lg">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="flex h-11 w-11 items-center justify-center rounded text-slate transition-colors hover:bg-surface-container-high hover:text-ink md:hidden"
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Ouvrir le menu de navigation"
              aria-expanded={menuOpen}
            >
              <Icon name="menu" />
            </button>
            <div className="relative hidden w-96 sm:block">
              <label htmlFor="recherche-globale" className="sr-only">
                Rechercher
              </label>
              <Icon
                name="search"
                className="pointer-events-none absolute left-sm top-1/2 -translate-y-1/2 text-[20px] text-outline"
              />
              <input
                id="recherche-globale"
                type="search"
                className="w-full rounded border border-outline-variant bg-limestone py-2.5 pl-xl pr-md font-body-sm text-ink outline-none transition-colors placeholder:text-outline focus:border-primary"
                placeholder="Rechercher entités, alertes…"
              />
            </div>
          </div>
          <div className="flex items-center gap-md">
            <span className="hidden font-body-sm text-slate sm:inline">{user?.nom}</span>
            <div className="mx-xs h-6 w-px bg-outline-variant" aria-hidden="true" />
            <button
              type="button"
              onClick={handleLogout}
              className="flex min-h-[44px] items-center gap-1.5 rounded px-3 text-slate transition-colors hover:bg-limestone hover:text-clay"
            >
              <Icon name="logout" />
              <span className="hidden font-label-caps lg:inline">Déconnexion</span>
            </button>
          </div>
        </header>

        <main id="contenu-principal" className="flex-1 overflow-y-auto bg-limestone">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
