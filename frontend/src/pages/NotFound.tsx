import { Link } from 'react-router-dom'
import Icon from '../components/Icon'

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-6 text-center">
      <Icon name="error" className="text-[64px] text-outline-variant" />
      <h1 className="mt-4 font-display text-display text-ink">404</h1>
      <p className="mt-2 font-body-lg text-body-lg text-slate">
        Cette page n'existe pas ou a été déplacée.
      </p>
      <Link
        to="/"
        className="mt-8 flex items-center gap-2 rounded bg-primary px-6 py-3 font-label-md text-label-md uppercase tracking-wider text-on-primary transition-colors hover:bg-surface-tint"
      >
        <Icon name="arrow_back" className="text-[18px]" />
        Retour au dashboard
      </Link>
    </div>
  )
}
