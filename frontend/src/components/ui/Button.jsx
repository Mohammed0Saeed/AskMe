import React from 'react'
import clsx from 'clsx'

const variants = {
  primary:   'bg-brand-500 text-white hover:bg-brand-600 shadow-soft active:bg-brand-700',
  secondary: 'bg-white text-warm-700 border border-warm-200 hover:bg-offwhite-200 active:bg-offwhite-300',
  ghost:     'text-warm-600 hover:bg-offwhite-200 hover:text-warm-900',
  danger:    'bg-red-600 text-white hover:bg-red-700 shadow-soft',
  outline:   'border border-brand-500 text-brand-600 hover:bg-brand-50',
}

const sizes = {
  xs: 'px-2.5 py-1 text-xs rounded-lg',
  sm: 'px-3 py-1.5 text-sm rounded-xl',
  md: 'px-4 py-2 text-sm rounded-xl',
  lg: 'px-5 py-2.5 text-base rounded-xl',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className,
  loading,
  icon: Icon,
  ...props
}) {
  return (
    <button
      {...props}
      disabled={loading || props.disabled}
      className={clsx(
        'inline-flex items-center gap-2 font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {loading && (
        <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      )}
      {!loading && Icon && <Icon size={14} />}
      {children}
    </button>
  )
}
