import React from 'react'
import clsx from 'clsx'

const variants = {
  red:     'bg-brand-100 text-brand-700 border-brand-200',
  green:   'bg-emerald-50 text-emerald-700 border-emerald-200',
  yellow:  'bg-amber-50 text-amber-700 border-amber-200',
  blue:    'bg-blue-50 text-blue-700 border-blue-200',
  gray:    'bg-warm-100 text-warm-600 border-warm-200',
  orange:  'bg-orange-50 text-orange-700 border-orange-200',
  purple:  'bg-purple-50 text-purple-700 border-purple-200',
}

const ACCESS_COLORS = {
  public:       'green',
  internal:     'blue',
  confidential: 'orange',
  restricted:   'red',
}

const CONFIDENCE_COLORS = {
  HIGH:   'green',
  MEDIUM: 'yellow',
  LOW:    'red',
}

export default function Badge({ children, variant = 'gray', className }) {
  return (
    <span className={clsx(
      'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border',
      variants[variant] || variants.gray,
      className
    )}>
      {children}
    </span>
  )
}

export function AccessBadge({ level }) {
  return <Badge variant={ACCESS_COLORS[level] || 'gray'}>{level}</Badge>
}

export function ConfidenceBadge({ level, score }) {
  const pct = score != null ? ` · ${Math.round(score * 100)}%` : ''
  return <Badge variant={CONFIDENCE_COLORS[level] || 'gray'}>{level}{pct}</Badge>
}
