import React from 'react'
import clsx from 'clsx'

export function Input({ label, error, className, ...props }) {
  return (
    <div className="space-y-1">
      {label && <label className="block text-xs font-medium text-warm-700">{label}</label>}
      <input
        {...props}
        className={clsx(
          'w-full rounded-xl border border-offwhite-300 bg-white px-3 py-2 text-sm text-warm-900 placeholder:text-warm-400',
          'focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent',
          'disabled:bg-offwhite-200 disabled:cursor-not-allowed',
          error && 'border-brand-400 focus:ring-brand-400',
          className
        )}
      />
      {error && <p className="text-xs text-brand-600">{error}</p>}
    </div>
  )
}

export function Select({ label, error, children, className, ...props }) {
  return (
    <div className="space-y-1">
      {label && <label className="block text-xs font-medium text-warm-700">{label}</label>}
      <select
        {...props}
        className={clsx(
          'w-full rounded-xl border border-offwhite-300 bg-white px-3 py-2 text-sm text-warm-900',
          'focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent',
          'disabled:bg-offwhite-200 disabled:cursor-not-allowed',
          className
        )}
      >
        {children}
      </select>
      {error && <p className="text-xs text-brand-600">{error}</p>}
    </div>
  )
}

export function Textarea({ label, error, className, ...props }) {
  return (
    <div className="space-y-1">
      {label && <label className="block text-xs font-medium text-warm-700">{label}</label>}
      <textarea
        {...props}
        className={clsx(
          'w-full rounded-xl border border-offwhite-300 bg-white px-3 py-2 text-sm text-warm-900 placeholder:text-warm-400 resize-none',
          'focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent',
          className
        )}
      />
      {error && <p className="text-xs text-brand-600">{error}</p>}
    </div>
  )
}
