import type { ReactNode } from 'react'
import Modal from './Modal'
import Button from './Button'
import Icon from './Icon'

interface ConfirmDialogProps {
  title: string
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** Variante du bouton de confirmation. */
  variant?: 'clay' | 'primary' | 'danger'
  icon?: string
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Fenêtre de confirmation d'action (remplace window.confirm). */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  variant = 'clay',
  icon = 'help',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal title={title} onClose={onCancel} size="max-w-md">
      <div className="flex gap-4 p-md">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-container-high text-ink"
          aria-hidden="true"
        >
          <Icon name={icon} />
        </span>
        <div className="pt-1 font-body-md text-body-md text-on-surface">{message}</div>
      </div>
      <div className="flex justify-end gap-3 border-t border-outline-variant bg-surface px-md py-sm">
        <Button variant="outline" onClick={onCancel} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button variant={variant} onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}
