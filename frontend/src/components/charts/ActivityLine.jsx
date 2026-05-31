import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-offwhite-300 rounded-xl px-3 py-2 shadow-card text-xs">
      <p className="text-warm-500 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="font-medium text-warm-900">
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  )
}

export default function ActivityLine({ data = [] }) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-40 text-xs text-warm-400">
        No activity yet
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="brandGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#DE3919" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#DE3919" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#F0EBE3" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: '#A8A29E' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: '#A8A29E' }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="count"
          name="Queries"
          stroke="#DE3919"
          strokeWidth={2}
          fill="url(#brandGrad)"
          dot={false}
          activeDot={{ r: 4, fill: '#DE3919', strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
