import clsx from 'clsx'

const configs = {
  critical: { label: 'CRITICAL', className: 'bg-red-950 text-red-400 border border-red-800' },
  high:     { label: 'HIGH',     className: 'bg-orange-950 text-orange-400 border border-orange-800' },
  medium:   { label: 'MEDIUM',   className: 'bg-yellow-950 text-yellow-400 border border-yellow-800' },
  low:      { label: 'LOW',      className: 'bg-green-950 text-green-400 border border-green-800' },
}

export default function RiskBadge({ level }) {
  const config = configs[level?.toLowerCase()] || configs.low
  return (
    <span className={clsx('badge font-mono', config.className)}>
      {config.label}
    </span>
  )
}
