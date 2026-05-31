import React from 'react'
import clsx from 'clsx'

export default function Card({ children, className, padding = true, ...props }) {
  return (
    <div
      {...props}
      className={clsx(
        'bg-white rounded-2xl shadow-soft border border-offwhite-300',
        padding && 'p-5',
        className
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, description, action, className }) {
  return (
    <div className={clsx('flex items-start justify-between gap-4 mb-4', className)}>
      <div>
        <h2 className="text-base font-semibold text-warm-900">{title}</h2>
        {description && <p className="text-xs text-warm-500 mt-0.5">{description}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}
