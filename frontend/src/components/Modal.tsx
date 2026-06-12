import { useEffect, useId, useRef, type ReactNode } from 'react'
import Icon from './Icon'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  /** Largeur max (classe Tailwind). */
  size?: string
}

/**
 * Boîte de dialogue accessible : verrou de focus, fermeture Escape,
 * blocage du scroll d'arrière-plan, restauration du focus à la fermeture.
 */
export default function Modal({ title, onClose, children, size = 'max-w-lg' }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const titleId = useId()

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'

    // Focus le premier élément interactif du panneau.
    const focusables = panelRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    focusables?.[0]?.focus()

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab' || !focusables || focusables.length === 0) return
      // Piège de focus.
      const list = Array.from(focusables)
      const first = list[0]
      const last = list[list.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
      previouslyFocused?.focus?.()
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4 backdrop-blur-[2px]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`fade-in w-full ${size} rounded-lg border border-outline-variant bg-surface-container-lowest shadow-2xl`}
      >
        <div className="flex items-center justify-between border-b border-outline-variant bg-surface px-md py-sm">
          <h2 id={titleId} className="font-headline-md text-headline-md text-ink">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer la fenêtre"
            className="flex h-9 w-9 items-center justify-center rounded text-slate transition-colors hover:bg-surface-container-high hover:text-ink"
          >
            <Icon name="close" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
