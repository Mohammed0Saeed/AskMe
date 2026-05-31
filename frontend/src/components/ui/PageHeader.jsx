import React from 'react'

export default function PageHeader({ icon: Icon, title, description, action }) {
  return (
    <div className="flex items-center justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="w-9 h-9 bg-brand-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <Icon className="w-4.5 h-4.5 text-brand-600" size={18} />
          </div>
        )}
        <div>
          <h1 className="text-lg font-bold text-warm-900 leading-tight">{title}</h1>
          {description && <p className="text-xs text-warm-500 mt-0.5">{description}</p>}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}
