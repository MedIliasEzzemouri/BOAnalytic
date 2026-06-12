import type { ReactNode } from 'react'

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-full">
      {/* Panneau gauche — branding dark */}
      <div className="relative hidden w-5/12 flex-col justify-between overflow-hidden p-12 lg:flex" style={{ background: '#0b1a2e' }}>
        {/* PLASTIMA en haut */}
        <div className="z-10">
          <img src="/plastima-logo.png" alt="Plastima" className="h-7 w-auto opacity-80" />
        </div>

        {/* Logo BOAnalytic + tagline au centre */}
        <div className="z-10">
          <div className="mb-6 text-[36px] font-extrabold leading-none">
            <span style={{ color: '#f97316' }}>BO</span>
            <span className="text-white">Analytic</span>
          </div>
          <h2 className="mb-6 text-[38px] font-bold leading-[46px] text-white">
            750 pages de Bulletin Officiel,{' '}
            <span style={{ color: '#f97316' }}>analysées chaque semaine.</span>
          </h2>
          <p className="text-[16px] leading-relaxed" style={{ color: '#94a3b8' }}>
            Extraction · Classification ML · Détection d'entités · Matching contre vos partenaires.
          </p>
        </div>

        {/* Footer */}
        <div className="z-10">
          <span className="text-[13px]" style={{ color: '#475569' }}>
            Développé par Plastima Casablanca
          </span>
        </div>
      </div>

      {/* Panneau droit — formulaire */}
      <div className="relative flex w-full flex-col items-center justify-center overflow-y-auto lg:w-7/12" style={{ background: '#f1f5f9' }}>
        {/* Branding mobile */}
        <div className="mb-8 flex items-center gap-2 lg:hidden">
          <span className="text-[28px] font-extrabold">
            <span style={{ color: '#f97316' }}>BO</span>
            <span style={{ color: '#0b1a2e' }}>Analytic</span>
          </span>
        </div>

        <div className="fade-in w-full max-w-[460px] px-6">
          {children}
        </div>
      </div>
    </div>
  )
}
