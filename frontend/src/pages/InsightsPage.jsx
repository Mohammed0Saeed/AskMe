import React, { useEffect, useState } from 'react'
import { BarChart2, RefreshCw, FileText, TrendingUp } from 'lucide-react'
import { insights as insightApi, audit as auditApi } from '../api/client'
import Card, { CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import ConfidenceDonut from '../components/charts/ConfidenceDonut'
import DomainBar from '../components/charts/DomainBar'
import ActivityLine from '../components/charts/ActivityLine'

function StatTile({ label, value, sub, color = 'brand' }) {
  const colors = {
    brand:   'bg-brand-50 border-brand-200 text-brand-600',
    green:   'bg-emerald-50 border-emerald-200 text-emerald-600',
    amber:   'bg-amber-50 border-amber-200 text-amber-600',
    blue:    'bg-blue-50 border-blue-200 text-blue-600',
  }
  return (
    <div className={`rounded-2xl border p-4 ${colors[color]}`}>
      <p className="text-2xl font-bold text-warm-900">{value}</p>
      <p className="text-xs font-medium mt-0.5">{label}</p>
      {sub && <p className="text-[10px] text-warm-400 mt-1">{sub}</p>}
    </div>
  )
}

export default function InsightsPage() {
  const [data, setData]           = useState(null)
  const [auditEntries, setAudit]  = useState([])
  const [loading, setLoading]     = useState(true)
  const [report, setReport]       = useState('')
  const [reporting, setReporting] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      insightApi.stats().then(setData).catch(() => setData(null)),
      auditApi.list(200).then(setAudit).catch(() => setAudit([])),
    ]).finally(() => setLoading(false))
  }

  useEffect(load, [])

  const generateReport = async () => {
    setReporting(true)
    try {
      const res = await insightApi.report({})
      setReport(res.report || res.gap_report || '')
    } catch (err) {
      setReport(`Error: ${err.message}`)
    } finally {
      setReporting(false)
    }
  }

  // API returns { distribution: {HIGH,MEDIUM,LOW}, by_domain: {domain: {HIGH,MEDIUM,LOW}}, total }
  const distribution = data?.distribution || {}
  const byDomain     = data?.by_domain    || {}
  const totalQueries = data?.total        || 0

  const domainData = Object.entries(byDomain)
    .filter(([domain]) => domain && domain.toLowerCase() !== 'unknown')
    .map(([domain, counts]) => ({
      domain,
      count: (counts.HIGH || 0) + (counts.MEDIUM || 0) + (counts.LOW || 0),
    }))

  const highConfidence = distribution.HIGH  || 0
  const noData         = distribution.LOW   || 0

  // Flatten distribution into array for ConfidenceDonut
  const distEntries = Object.entries(distribution).map(([confidence_level, n]) =>
    Array(n).fill({ confidence_level })
  ).flat()

  const activityMap = auditEntries.reduce((acc, e) => {
    const d = (e.timestamp || '').slice(0, 10)
    if (d) acc[d] = (acc[d] || 0) + 1
    return acc
  }, {})
  const activityData = Object.entries(activityMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14)
    .map(([date, count]) => ({ date: date.slice(5), count }))

  return (
    <div className="p-6 space-y-5">
      <PageHeader
        icon={BarChart2}
        title="Insights"
        description="Usage analytics and knowledge-gap detection"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={RefreshCw} onClick={load} loading={loading}>Refresh</Button>
            <Button size="sm" icon={FileText} onClick={generateReport} loading={reporting}>Gap report</Button>
          </div>
        }
      />

      {/* KPI tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile label="Total queries" value={totalQueries} color="brand" />
        <StatTile label="High confidence" value={`${totalQueries ? Math.round((highConfidence / totalQueries) * 100) : 0}%`} sub={`${highConfidence} of ${totalQueries}`} color="green" />
        <StatTile label="No-data answers" value={noData} sub="knowledge gaps found" color="amber" />
        <StatTile label="Domains tracked" value={domainData.length} color="blue" />
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader title="Confidence distribution" description="HIGH / MEDIUM / LOW breakdown" />
          <ConfidenceDonut data={distEntries} />
        </Card>

        <Card>
          <CardHeader title="Queries by domain" />
          <DomainBar data={domainData} dataKey="count" label="Queries" />
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Query activity" description="Last 14 days" />
          <ActivityLine data={activityData} />
        </Card>
      </div>

      {/* Gap report */}
      {report && (
        <Card>
          <CardHeader title="Knowledge-gap report" icon={TrendingUp} />
          <div className="prose prose-sm max-w-none text-warm-700 text-xs leading-relaxed whitespace-pre-wrap font-mono bg-offwhite-100 rounded-xl p-4">
            {report}
          </div>
        </Card>
      )}
    </div>
  )
}
