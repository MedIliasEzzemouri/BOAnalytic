import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { alertesApi, statsApi, exportsApi, errorMessage } from '../api/client'
import type { Alerte, Stats } from '../types'
import { ErrorBox } from '../components/ui'
import { Skeleton } from '../components/Skeleton'
import { StatutAlerteBadge } from '../components/badges'
import { formatDateTime } from '../lib/format'
import Button from '../components/Button'
import Icon from '../components/Icon'

interface KpiProps {
  value: string | number
  label: string
  icon: string
  accent?: boolean
}

function Kpi({ value, label, icon, accent }: KpiProps) {
  return (
    <div
      className={`col-span-12 flex items-center gap-4 rounded-lg border p-5 transition-shadow duration-200 hover:shadow-md md:col-span-3 ${
        accent
          ? 'border-clay bg-primary-fixed'
          : 'border-outline-variant bg-surface-container-lowest'
      }`}
    >
      <span
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${
          accent ? 'bg-clay text-white' : 'bg-surface-container-high text-ink'
        }`}
        aria-hidden="true"
      >
        <Icon name={icon} />
      </span>
      <div className="min-w-0">
        <div
          className={`font-headline-lg text-headline-lg leading-none ${
            accent ? 'text-clay' : 'text-ink'
          }`}
        >
          {value}
        </div>
        <div className={`mt-1.5 font-body-sm ${accent ? 'font-medium text-clay' : 'text-slate'}`}>
          {label}
        </div>
      </div>
    </div>
  )
}

const PERIODES: Array<{ label: string; value: number | null }> = [
  { label: '7 derniers jours', value: 7 },
  { label: '30 j', value: 30 },
  { label: '90 j', value: 90 },
  { label: 'Tout', value: null },
]

/** Sélecteur de période des KPI (contrôle segmenté). */
function PeriodSelector({
  value,
  onChange,
  busy,
}: {
  value: number | null
  onChange: (v: number | null) => void
  busy?: boolean
}) {
  return (
    <div
      role="group"
      aria-label="Période d'affichage des indicateurs"
      className="flex items-center gap-1 rounded-lg border border-outline-variant bg-surface-container-low p-1"
    >
      {busy && (
        <Icon
          name="progress_activity"
          className="ml-1 animate-spin text-[16px] text-slate"
        />
      )}
      {PERIODES.map((p) => (
        <button
          key={p.label}
          type="button"
          onClick={() => onChange(p.value)}
          aria-pressed={value === p.value}
          className={`min-h-[36px] whitespace-nowrap rounded px-3 py-1.5 font-label-md text-label-md transition-colors duration-200 ${
            value === p.value
              ? 'bg-surface-container-lowest text-ink shadow-sm'
              : 'text-slate hover:text-ink'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto flex w-full max-w-container-max flex-col gap-gutter">
        <Skeleton className="h-56 w-full rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-80" />
        </div>
        <div className="grid grid-cols-12 gap-gutter">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="col-span-12 h-24 rounded-lg md:col-span-3" />
          ))}
        </div>
        <div className="grid grid-cols-12 gap-gutter">
          <Skeleton className="col-span-12 h-72 rounded-lg md:col-span-4" />
          <Skeleton className="col-span-12 h-72 rounded-lg md:col-span-8" />
        </div>
        <div className="grid grid-cols-12 gap-gutter">
          <Skeleton className="col-span-12 h-64 rounded-lg md:col-span-5" />
          <Skeleton className="col-span-12 h-64 rounded-lg md:col-span-7" />
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [priorites, setPriorites] = useState<Record<string, number>>({})
  const [topTiers, setTopTiers] = useState<Array<{ nom: string; nb_alertes: number }>>([])
  const [recentes, setRecentes] = useState<Alerte[]>([])
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Période d'affichage des KPI : null = depuis le début.
  const [periode, setPeriode] = useState<number | null>(null)

  // Données indépendantes de la période (chargées une seule fois).
  useEffect(() => {
    Promise.all([statsApi.parPriorite(), statsApi.topTiers(5), alertesApi.list()])
      .then(([p, t, alertes]) => {
        setPriorites(p)
        setTopTiers(t)
        setRecentes(alertes.slice(0, 5))
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  // KPI : rechargés à chaque changement de période.
  useEffect(() => {
    setStatsLoading(true)
    statsApi
      .get(periode)
      .then(setStats)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setStatsLoading(false))
  }, [periode])

  // Téléchargement du rapport PDF.
  const [exporting, setExporting] = useState(false)
  async function handleExportPdf() {
    setExporting(true)
    setError(null)
    try {
      // « Tout » → on couvre l'année écoulée (limite max de l'endpoint).
      await exportsApi.rapportGlobal(periode ?? 365)
    } catch (err) {
      setError(errorMessage(err, 'Échec de la génération du rapport PDF.'))
    } finally {
      setExporting(false)
    }
  }

  if (loading || !stats) return <DashboardSkeleton />

  const periodeLabel =
    periode == null ? 'depuis le début' : `sur les ${periode} derniers jours`

  if (error) {
    return (
      <div className="p-gutter">
        <ErrorBox message={error} />
      </div>
    )
  }

  const totalPrio = Object.values(priorites).reduce((a, b) => a + b, 0) || 1
  const haute = priorites.haute ?? 0
  const moyenne = priorites.moyenne ?? 0
  const basse = priorites.basse ?? 0

  const typeEntries = Object.entries(stats?.par_type ?? {})
  const maxType = Math.max(1, ...typeEntries.map(([, v]) => v))
  const maxTier = Math.max(1, ...topTiers.map((t) => t.nb_alertes))

  return (
    <div className="fade-in p-gutter">
      <div className="mx-auto flex w-full max-w-container-max flex-col gap-gutter">
        {/* Masthead officiel — Bulletin Officiel du Royaume du Maroc */}
        <section
          aria-label="Bulletin Officiel du Royaume du Maroc"
          className="overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest shadow-sm"
        >
          <div className="h-1.5 w-full bg-clay" aria-hidden="true" />
          <div className="flex flex-col items-center gap-4 px-6 py-9">
            <img
              src="/jarida-rasmiya.png"
              alt="Bulletin Officiel du Royaume du Maroc — الجريدة الرسمية"
              className="h-32 w-auto object-contain sm:h-40 lg:h-44"
            />
            <div className="flex items-center gap-3 text-slate">
              <span className="h-px w-10 bg-outline-variant" aria-hidden="true" />
              <span className="text-center font-label-caps text-label-caps uppercase tracking-[0.18em]">
                Veille juridique automatisée · Plastima Casablanca
              </span>
              <span className="h-px w-10 bg-outline-variant" aria-hidden="true" />
            </div>
          </div>
        </section>

        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-1">
            <h1 className="font-headline-lg text-headline-lg text-ink">Dashboard</h1>
            <p className="font-body-md text-slate">
              Synthèse de la veille juridique — Plastima Casablanca · KPI {periodeLabel}.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <PeriodSelector value={periode} onChange={setPeriode} busy={statsLoading} />
            <Button
              variant="outline"
              icon="picture_as_pdf"
              loading={exporting}
              onClick={handleExportPdf}
            >
              {exporting ? 'Génération…' : 'Télécharger le rapport PDF'}
            </Button>
          </div>
        </header>

        {/* KPI */}
        <section
          aria-label="Indicateurs clés"
          aria-busy={statsLoading}
          className={`grid grid-cols-12 gap-gutter transition-opacity duration-200 ${
            statsLoading ? 'opacity-60' : 'opacity-100'
          }`}
        >
          <Kpi
            icon="description"
            value={stats?.total_bulletins ?? 0}
            label="Bulletins traités"
          />
          <Kpi
            icon="campaign"
            value={(stats?.total_annonces_legales ?? 0) + (stats?.total_annonces_judiciaires ?? 0)}
            label="Annonces détectées"
          />
          <Kpi icon="groups" value={stats?.total_tiers ?? 0} label="Partenaires actifs" />
          <Kpi
            icon="notifications_active"
            value={stats?.alertes_nouvelles ?? 0}
            label="Nouvelles alertes"
            accent
          />
        </section>

        {/* Graphiques */}
        <section className="grid grid-cols-12 gap-gutter">
          {/* Alertes par priorité */}
          <div className="col-span-12 flex flex-col rounded-lg border border-outline-variant bg-surface-container-lowest p-md md:col-span-4">
            <h2 className="mb-4 border-b border-outline-variant pb-2 font-headline-md text-headline-md text-ink">
              Alertes par priorité
            </h2>
            <div className="relative flex min-h-[200px] flex-1 flex-col items-center justify-center">
              <div
                className="h-40 w-40 rounded-full"
                role="img"
                aria-label={`Répartition des alertes : ${haute} haute, ${moyenne} moyenne, ${basse} basse`}
                style={{
                  background: `conic-gradient(#B8422E 0 ${(haute / totalPrio) * 360}deg, #1A1C1E ${
                    (haute / totalPrio) * 360
                  }deg ${((haute + moyenne) / totalPrio) * 360}deg, #e4e2df ${
                    ((haute + moyenne) / totalPrio) * 360
                  }deg 360deg)`,
                }}
              >
                <div className="absolute left-1/2 top-1/2 flex h-24 w-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full border border-outline-variant bg-surface-container-lowest">
                  <span className="font-headline-md font-bold leading-none text-ink">
                    {stats?.total_alertes ?? 0}
                  </span>
                  <span className="mt-1 text-[10px] font-bold uppercase tracking-tighter text-outline">
                    Total
                  </span>
                </div>
              </div>
              <div className="mt-md flex flex-wrap justify-center gap-md font-body-sm">
                <span className="flex items-center gap-xs">
                  <span className="h-3 w-3 rounded-sm bg-clay" aria-hidden="true" /> Haute ({haute})
                </span>
                <span className="flex items-center gap-xs">
                  <span className="h-3 w-3 rounded-sm bg-ink" aria-hidden="true" /> Moyenne (
                  {moyenne})
                </span>
                <span className="flex items-center gap-xs">
                  <span className="h-3 w-3 rounded-sm bg-surface-variant" aria-hidden="true" /> Basse
                  ({basse})
                </span>
              </div>
            </div>
          </div>

          {/* Annonces par type */}
          <div className="col-span-12 flex flex-col rounded-lg border border-outline-variant bg-surface-container-lowest p-md md:col-span-8">
            <h2 className="mb-4 border-b border-outline-variant pb-2 font-headline-md text-headline-md text-ink">
              Annonces par type
            </h2>
            {typeEntries.length === 0 ? (
              <p className="flex flex-1 items-center justify-center font-body-sm text-slate">
                Aucune donnée disponible.
              </p>
            ) : (
              <div className="mt-auto flex min-h-[200px] flex-1 items-end gap-md">
                {typeEntries.map(([type, count]) => (
                  <div key={type} className="group flex flex-1 flex-col items-center gap-xs">
                    <div
                      className="flex w-full max-w-[60px] items-end justify-center bg-primary-fixed transition-colors duration-200 group-hover:bg-clay group-hover:text-white"
                      style={{ height: `${20 + (count / maxType) * 160}px` }}
                    >
                      <span className="mb-sm font-label-caps">{count}</span>
                    </div>
                    <span className="w-full truncate text-center font-body-sm capitalize text-slate">
                      {type}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Tableaux */}
        <section className="grid grid-cols-12 gap-gutter">
          {/* Top tiers */}
          <div className="col-span-12 rounded-lg border border-outline-variant bg-surface-container-lowest p-md md:col-span-5">
            <h2 className="mb-4 border-b border-outline-variant pb-2 font-headline-md text-headline-md text-ink">
              Top 5 Tiers (alertes)
            </h2>
            {topTiers.length === 0 ? (
              <p className="font-body-sm text-slate">Aucune alerte enregistrée.</p>
            ) : (
              <div className="mt-4 space-y-sm">
                {topTiers.map((t) => (
                  <div key={t.nom} className="flex items-center gap-md">
                    <div className="w-32 truncate font-label-mono text-ink" title={t.nom}>
                      {t.nom}
                    </div>
                    <div className="h-6 flex-1 overflow-hidden rounded-sm bg-limestone">
                      <div
                        className="h-full bg-ink transition-all duration-500"
                        style={{ width: `${(t.nb_alertes / maxTier) * 100}%` }}
                      />
                    </div>
                    <div className="w-12 text-right font-body-sm text-slate">{t.nb_alertes}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dernières alertes */}
          <div className="col-span-12 overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest md:col-span-7">
            <h2 className="m-4 mb-2 border-b border-outline-variant pb-2 font-headline-md text-headline-md text-ink">
              Dernières alertes
            </h2>
            {recentes.length === 0 ? (
              <p className="p-md font-body-sm text-slate">Aucune alerte récente.</p>
            ) : (
              <table className="mt-2 w-full border-collapse text-left">
                <caption className="sr-only">Cinq alertes les plus récentes</caption>
                <thead className="border-y border-outline-variant bg-limestone font-label-mono text-ink">
                  <tr>
                    <th scope="col" className="px-4 py-3">Date</th>
                    <th scope="col" className="px-4 py-3">Alerte</th>
                    <th scope="col" className="px-4 py-3">Statut</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant font-body-sm text-ink">
                  {recentes.map((a) => (
                    <tr key={a.id} className="transition-colors hover:bg-limestone">
                      <td className="whitespace-nowrap px-4 py-4 text-outline">
                        {formatDateTime(a.created_at)}
                      </td>
                      <td className="px-4 py-4">
                        <Link
                          to={`/alertes/${a.id}`}
                          className="rounded font-medium text-ink hover:underline"
                        >
                          {a.nom_detecte}
                        </Link>
                        <div className="mt-1 text-sm text-slate">
                          Tier : {a.nom_tier}
                          {a.type_annonce ? ` · ${a.type_annonce}` : ''}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <StatutAlerteBadge statut={a.statut} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="border-t border-outline-variant bg-limestone p-sm text-center">
              <Link
                to="/alertes"
                className="inline-flex items-center justify-center gap-1 rounded px-2 py-1 font-label-mono font-bold text-ink hover:underline"
              >
                Voir toutes les alertes
                <Icon name="chevron_right" className="text-[16px]" />
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
