interface IconProps {
  name: string
  className?: string
  fill?: boolean
}

/** Material Symbols Outlined. */
export default function Icon({ name, className = '', fill = false }: IconProps) {
  return (
    <span className={`material-symbols-outlined ${fill ? 'fill' : ''} ${className}`}>
      {name}
    </span>
  )
}
