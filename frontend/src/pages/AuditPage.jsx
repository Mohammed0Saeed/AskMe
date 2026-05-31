import React, { useEffect, useState } from 'react'
import { ClipboardList, RefreshCw, MessageSquare, ChevronRight, User, Bot } from 'lucide-react'
import { audit as auditApi } from '../api/client'
import Card, { CardHeader } from '../components/ui/Card'
import { ConfidenceBadge, AccessBadge } from '../components/ui/Badge'
import PageHeader from '../components/ui/PageHeader'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'

/** Each audit entry has both `query` (user) and `answer` (AI). Expand into two turns. */
function entriesToTurns(entries) {
  return entries.flatMap((e) => [
    { role: 'user',      text: e.query,  ts: e.timestamp, name: e.user_name || 'User' },
    { role: 'assistant', text: e.answer, ts: e.timestamp, confidence: e.confidence, model: e.model, citations: e.citations },
  ])
}

function Bubble({ turn }) {
  const isUser = turn.role === 'user'
  return (
    <div className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${isUser ? 'bg-brand-500' : 'bg-warm-200'}`}>
        {isUser
          ? <User size={13} className="text-white" />
          : <Bot  size={13} className="text-warm-600" />}
      </div>

      <div className={`max-w-[78%] space-y-1 ${isUser ? 'items-end flex flex-col' : ''}`}>
        {/* Name + time */}
        <p className="text-[10px] text-warm-400 px-1">
          {isUser ? turn.name : `AskMe · ${turn.model || ''}`}
          {turn.ts && ` · ${new Date(turn.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
        </p>

        {/* Bubble */}
        <div className={`text-xs px-3.5 py-2.5 rounded-2xl leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-brand-500 text-white rounded-tr-sm'
            : 'bg-offwhite-100 border border-offwhite-300 text-warm-800 rounded-tl-sm'
        }`}>
          {turn.text}
        </div>

        {/* AI metadata row */}
        {!isUser && turn.confidence && (
          <div className="flex items-center gap-2 px-1 flex-wrap">
            <ConfidenceBadge level={turn.confidence.level} score={turn.confidence.score} />
            {turn.citations?.length > 0 && (
              <span className="text-[10px] text-warm-400">
                {turn.citations.length} source{turn.citations.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ConvModal({ auditId, onClose }) {
  const [turns, setTurns]     = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auditId) return
    setLoading(true)
    setTurns([])
    auditApi.get(auditId)
      .then((entry) => {
        const convId = entry.conversation_id
        if (convId) {
          return auditApi.conversation(convId).then((entries) => {
            // conversation returns array of audit entries, each with query+answer
            const arr = Array.isArray(entries) ? entries : [entries]
            setTurns(entriesToTurns(arr))
          })
        }
        // Single entry fallback
        setTurns(entriesToTurns([entry]))
      })
      .catch(() => setTurns([]))
      .finally(() => setLoading(false))
  }, [auditId])

  return (
    <Modal open={!!auditId} onClose={onClose} title="Conversation" size="lg">
      {loading ? (
        <div className="flex items-center justify-center py-10">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : turns.length === 0 ? (
        <p className="text-xs text-warm-400 text-center py-8">No conversation data found.</p>
      ) : (
        <div className="space-y-4 max-h-[62vh] overflow-y-auto pr-1">
          {turns.map((t, i) => <Bubble key={i} turn={t} />)}
        </div>
      )}
    </Modal>
  )
}

function AuditRow({ entry, onOpen }) {
  return (
    <div
      onClick={() => onOpen(entry.audit_id)}
      className="flex items-center gap-3 px-4 py-3 bg-white border border-offwhite-200 rounded-xl hover:border-brand-200 hover:bg-brand-50/30 cursor-pointer transition-all group"
    >
      <div className="w-8 h-8 bg-offwhite-200 rounded-xl flex items-center justify-center flex-shrink-0">
        <MessageSquare size={14} className="text-warm-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-warm-900 truncate">{entry.query}</p>
        <p className="text-[10px] text-warm-400 mt-0.5">{entry.user_name || entry.user_id} · {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '—'}</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {entry.confidence && <ConfidenceBadge level={entry.confidence.level} />}
        {entry.access_level && <AccessBadge level={entry.access_level} />}
        <ChevronRight size={12} className="text-warm-300 group-hover:text-brand-400 transition-all" />
      </div>
    </div>
  )
}

export default function AuditPage() {
  const [entries, setEntries]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)

  const load = () => {
    setLoading(true)
    auditApi.list(50)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div className="p-6 space-y-5">
      <PageHeader
        icon={ClipboardList}
        title="Audit Log"
        description="Recent queries and responses"
        action={
          <Button variant="secondary" size="sm" onClick={load} loading={loading} icon={RefreshCw}>
            Refresh
          </Button>
        }
      />

      <Card padding={false}>
        <CardHeader
          title={`${entries.length} entries`}
          className="px-5 pt-5"
        />
        {loading && entries.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <EmptyState icon={ClipboardList} title="No audit entries yet" description="Queries will appear here after users interact with AskMe." />
        ) : (
          <div className="space-y-1.5 p-3">
            {entries.map((e) => (
              <AuditRow key={e.audit_id} entry={e} onOpen={setSelected} />
            ))}
          </div>
        )}
      </Card>

      <ConvModal auditId={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
