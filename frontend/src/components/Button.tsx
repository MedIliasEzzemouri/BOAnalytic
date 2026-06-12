import type { ButtonHTMLAttributes, ReactNode } from 'react'
import Icon from './Icon'

type Variant = 'primary' | 'clay' | 'outline' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: string
  children?: ReactNode
}

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-surface-tint',
  clay: 'bg-clay text-white hover:bg-primary',
  outline:
    'border border-outline-variant bg-transparent text-ink hover:bg-surface-container-high',
  ghost: 'bg-transparent text-secondary hover:bg-surface-container-high hover:text-ink',
  danger: 'border border-error/40 bg-transparent text-error hover:bg-error-container',
}

const SIZES: Record<Size, string> = {
  sm: 'min-h-[36px] px-3 py-1.5 text-label-md',
  md: 'min-h-[44px] px-5 py-2.5 text-label-md',
}

/** Bouton cohérent : variantes, état de chargement, cible tactile ≥ 44px. */
export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded font-label-md uppercase tracking-wider transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading ? (
        <Icon name="progress_activity" className="animate-spin text-[18px]" />
      ) : (
        icon && <Icon name={icon} className="text-[18px]" />
      )}
      {children}
    </button>
  )
}
