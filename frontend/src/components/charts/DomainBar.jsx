import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

const PALETTE = [
  '#DE3919', '#F06650', '#F68F7A', '#FAB9AA',
  '#10B981', '#F59E0B', '#6366F1', '#EC4899',
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-offwhite-300 rounded-xl px-3 py-2 shadow-card text-xs">
      <p className="font-semibold text-warm-900 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-warm-600">
          {p.name}: <span className="font-medium text-warm-900">{p.value}</span>
        </p>
      ))}
    </div>
  )
}

export default function DomainBar({ data = [], dataKey = 'count', label = 'Queries' }) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-xs text-warm-400">
        No data yet
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#F0EBE3" vertical={false} />
        <XAxis
          dataKey="domain"
          tick={{ fontSize: 11, fill: '#78716C' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#78716C' }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F8F5F0' }} />
        <Bar dataKey={dataKey} name={label} radius={[6, 6, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
