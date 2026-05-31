import React from 'react'

export default function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && (
        <div className="w-12 h-12 bg-offwhite-200 rounded-2xl flex items-center justify-center mb-3">
          <Icon className="w-6 h-6 text-warm-400" />
        </div>
      )}
      <p className="text-sm font-medium text-warm-700">{title}</p>
      {description && <p className="text-xs text-warm-400 mt-1 max-w-xs">{description}</p>}
    </div>
  )
}
