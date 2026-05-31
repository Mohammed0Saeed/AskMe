import React, { useEffect, useState } from 'react'
import { Database, RefreshCw, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { kb as kbApi } from '../api/client'
import Card, { CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { AccessBadge } from '../components/ui/Badge'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'

function DomainSection({ domain, docs }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="border border-offwhite-300 rounded-2xl overflow-hidden bg-white shadow-soft">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 bg-offwhite-50 hover:bg-offwhite-100 transition-all"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-warm-900">{domain}</span>
          <span className="text-[11px] bg-offwhite-200 text-warm-500 px-2 py-0.5 rounded-full">{docs.length} docs</span>
        </div>
        {open ? <ChevronUp size={14} className="text-warm-400" /> : <ChevronDown size={14} className="text-warm-400" />}
      </button>

      {open && (
        <div className="divide-y divide-offwhite-100">
          {docs.map((doc, i) => (
            <div key={i} className="flex items-center gap-3 px-5 py-3">
              <FileText size={14} className="text-brand-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-warm-900 truncate">{doc.source_file}</p>
                <p className="text-[10px] text-warm-400 mt-0.5">
                  {doc.chunk_count} chunks · {doc.author || '—'}
                </p>
              </div>
              <AccessBadge level={doc.access_level} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function KBPage() {
  const [docs, setDocs]     = useState([])
  const [stats, setStats]   = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([
      kbApi.documents().then(setDocs).catch(() => []),
      kbApi.stats().then(setStats).catch(() => null),
    ]).finally(() => setLoading(false))
  }

  useEffect(load, [])

  // Group by domain
  const byDomain = docs.reduce((acc, doc) => {
    const d = doc.domain || 'General'
    if (!acc[d]) acc[d] = []
    acc[d].push(doc)
    return acc
  }, {})

  return (
    <div className="p-6 space-y-5">
      <PageHeader
        icon={Database}
        title="Knowledge Base"
        description="Browse all ingested documents"
        action={
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={load} loading={loading}>
            Refresh
          </Button>
        }
      />

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { label: 'Total chunks', value: stats.total_chunks ?? stats.chunk_count ?? 0 },
            { label: 'Documents', value: docs.length },
            { label: 'Domains', value: Object.keys(byDomain).length },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border border-offwhite-300 rounded-2xl p-4 shadow-soft text-center">
              <p className="text-xl font-bold text-warm-900">{value}</p>
              <p className="text-[11px] text-warm-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : Object.keys(byDomain).length === 0 ? (
        <EmptyState icon={Database} title="No documents ingested yet" description="Upload files via the Ingest page to populate the knowledge base" />
      ) : (
        <div className="space-y-3">
          {Object.entries(byDomain).sort(([a], [b]) => a.localeCompare(b)).map(([domain, ds]) => (
            <DomainSection key={domain} domain={domain} docs={ds} />
          ))}
        </div>
      )}
    </div>
  )
}
