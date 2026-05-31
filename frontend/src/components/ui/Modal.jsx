import React, { useEffect } from 'react'
import { X } from 'lucide-react'
import clsx from 'clsx'

export default function Modal({ open, onClose, title, children, size = 'md' }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose?.() }
    if (open) document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const widths = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.() }}
    >
      <div className="absolute inset-0 bg-warm-900/40 backdrop-blur-sm" />
      <div className={clsx('relative bg-white rounded-2xl shadow-elevated w-full', widths[size])}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-offwhite-300">
          <h3 className="text-base font-semibold text-warm-900">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-xl p-1.5 text-warm-400 hover:text-warm-700 hover:bg-offwhite-200 transition-all"
          >
            <X size={16} />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
