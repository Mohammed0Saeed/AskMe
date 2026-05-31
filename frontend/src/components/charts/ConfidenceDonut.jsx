import React from 'react'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  HIGH:   '#10B981',
  MEDIUM: '#F59E0B',
  LOW:    '#DE3919',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  return (
    <div className="bg-white border border-offwhite-300 rounded-xl px-3 py-2 shadow-card text-xs">
      <span className="font-semibold text-warm-900">{name}</span>
      <span className="text-warm-500 ml-1">— {value} queries</span>
    </div>
  )
}

const renderLegend = ({ payload }) => (
  <ul className="flex flex-col gap-1.5 mt-2">
    {payload.map(({ value, color, payload: p }) => (
      <li key={value} className="flex items-center gap-2 text-xs text-warm-700">
        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
        <span className="font-medium">{value}</span>
        <span className="text-warm-400 ml-auto">{p.value}</span>
      </li>
    ))}
  </ul>
)

export default function ConfidenceDonut({ data = [] }) {
  const chartData = Object.entries(
    data.reduce((acc, { confidence_level }) => {
      const key = (confidence_level || 'LOW').toUpperCase()
      acc[key] = (acc[key] || 0) + 1
      return acc
    }, {})
  ).map(([name, value]) => ({ name, value, fill: COLORS[name] || '#A8A29E' }))

  if (!chartData.length) {
    return (
      <div className="flex items-center justify-center h-40 text-xs text-warm-400">
        No data yet
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          cx="40%"
          cy="50%"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={3}
          dataKey="value"
          stroke="none"
        >
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={entry.fill} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          layout="vertical"
          align="right"
          verticalAlign="middle"
          content={renderLegend}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
