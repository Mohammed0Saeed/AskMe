import React, { useEffect, useRef, useState } from 'react'
import { Send, MessageSquare, ChevronDown, ChevronUp, FileText, Sliders } from 'lucide-react'
import { ask as askApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { ConfidenceBadge, AccessBadge } from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Select } from '../components/ui/Input'
import clsx from 'clsx'

const DOMAINS = ['', 'Legal', 'Customer Service', 'HR', 'Finance', 'Technology', 'Operations', 'Marketing', 'Data Procurement', 'Other']
const ACCESS  = ['', 'public', 'internal', 'confidential', 'restricted']

function Citation({ cite, index }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-offwhite-300 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-offwhite-50 hover:bg-offwhite-100 text-left transition-all"
      >
        <span className="text-[10px] font-bold text-brand-500 bg-brand-100 rounded-md px-1.5 py-0.5">REF-{index + 1}</span>
        <span className="text-xs font-medium text-warm-700 truncate flex-1">{cite.source_file}</span>
        {cite.page_number && <span className="text-[10px] text-warm-400">p.{cite.page_number}</span>}
        <AccessBadge level={cite.access_level} />
        {open ? <ChevronUp size={12} className="text-warm-400 flex-shrink-0" /> : <ChevronDown size={12} className="text-warm-400 flex-shrink-0" />}
      </button>
      {open && cite.relevant_quote && (
        <div className="px-3 py-2 text-xs text-warm-600 bg-white border-t border-offwhite-200 italic leading-relaxed">
          "{cite.relevant_quote}"
        </div>
      )}
    </div>
  )
}

function ChatBubble({ msg }) {
  const [showCites, setShowCites] = useState(false)
  const isUser = msg.role === 'user'

  return (
    <div className={clsx('flex gap-3', isUser && 'flex-row-reverse')}>
      <div className={clsx(
        'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-1',
        isUser ? 'bg-brand-500 text-white' : 'bg-warm-200 text-warm-600'
      )}>
        {isUser ? 'U' : 'AI'}
      </div>
      <div className={clsx('max-w-[75%] space-y-2', isUser && 'items-end flex flex-col')}>
        <div className={clsx(
          'rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-brand-500 text-white rounded-tr-sm'
            : 'bg-white border border-offwhite-300 text-warm-900 rounded-tl-sm shadow-soft'
        )}>
          {msg.content}
        </div>

        {/* Assistant metadata */}
        {!isUser && (msg.confidence || msg.citations?.length > 0) && (
          <div className="flex items-center gap-2 flex-wrap">
            {msg.confidence && (
              <ConfidenceBadge level={msg.confidence.level} score={msg.confidence.score} />
            )}
            {msg.model && (
              <span className="text-[10px] text-warm-400 bg-offwhite-200 px-2 py-0.5 rounded-full">
                {msg.model}
              </span>
            )}
            {msg.tokenUsage && (
              <span className="text-[10px] text-warm-400">
                {msg.tokenUsage.total_tokens} tokens
              </span>
            )}
            {msg.citations?.length > 0 && (
              <button
                onClick={() => setShowCites((s) => !s)}
                className="text-[10px] text-brand-600 hover:text-brand-700 font-medium"
              >
                {showCites ? 'Hide' : 'Show'} {msg.citations.length} source{msg.citations.length !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        )}

        {!isUser && showCites && msg.citations?.length > 0 && (
          <div className="space-y-1.5 w-full">
            {msg.citations.map((c, i) => <Citation key={i} cite={c} index={i} />)}
          </div>
        )}
      </div>
    </div>
  )
}

export default function AskPage() {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [convId]                = useState(() => crypto.randomUUID())
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState({ access_level: '', domain: '', top_k: 5 })
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: q }])
    setLoading(true)
    try {
      const payload = {
        query: q,
        conversation_id: convId,
        top_k: Number(filters.top_k) || 5,
        ...(filters.access_level && { access_level: filters.access_level }),
        ...(filters.domain && { domain: filters.domain }),
      }
      const res = await askApi.query(payload)
      setMessages((m) => [...m, {
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        confidence: res.confidence,
        model: res.model,
        tokenUsage: res.token_usage,
      }])
    } catch (err) {
      setMessages((m) => [...m, {
        role: 'assistant',
        content: `Error: ${err.message}`,
        citations: [],
      }])
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-offwhite-300 bg-white">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand-100 rounded-xl flex items-center justify-center">
            <MessageSquare size={16} className="text-brand-600" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-warm-900">Ask AskMe</h1>
            <p className="text-[11px] text-warm-400">RAG-powered answers from internal documents</p>
          </div>
        </div>
        <button
          onClick={() => setShowFilters((s) => !s)}
          className={clsx(
            'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl border transition-all',
            showFilters
              ? 'bg-brand-50 border-brand-300 text-brand-700'
              : 'bg-white border-offwhite-300 text-warm-600 hover:bg-offwhite-100'
          )}
        >
          <Sliders size={12} />
          Filters
        </button>
      </div>

      {/* Filter bar */}
      {showFilters && (
        <div className="flex items-center gap-3 px-6 py-3 bg-offwhite-50 border-b border-offwhite-200">
          <Select
            value={filters.access_level}
            onChange={(e) => setFilters((f) => ({ ...f, access_level: e.target.value }))}
            className="w-36 text-xs py-1.5"
          >
            {ACCESS.map((a) => <option key={a} value={a}>{a || 'All access'}</option>)}
          </Select>
          <Select
            value={filters.domain}
            onChange={(e) => setFilters((f) => ({ ...f, domain: e.target.value }))}
            className="w-44 text-xs py-1.5"
          >
            {DOMAINS.map((d) => <option key={d} value={d}>{d || 'All domains'}</option>)}
          </Select>
          <Select
            value={filters.top_k}
            onChange={(e) => setFilters((f) => ({ ...f, top_k: e.target.value }))}
            className="w-24 text-xs py-1.5"
          >
            {[3, 5, 8, 10].map((k) => <option key={k} value={k}>Top {k}</option>)}
          </Select>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-16">
            <div className="w-14 h-14 bg-brand-100 rounded-2xl flex items-center justify-center mb-4">
              <MessageSquare size={24} className="text-brand-500" />
            </div>
            <h2 className="text-base font-semibold text-warm-800 mb-1">Ask anything</h2>
            <p className="text-sm text-warm-400 max-w-sm">
              Ask questions about SIX Group policies, procedures, and internal documents.
            </p>
            <div className="grid grid-cols-2 gap-2 mt-6 max-w-md">
              {[
                'What is the leave policy?',
                'Explain the expense reimbursement process',
                'What are the data privacy rules?',
                'How do I submit an IT ticket?',
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); }}
                  className="text-left text-xs px-3 py-2.5 bg-white border border-offwhite-300 rounded-xl hover:bg-offwhite-100 hover:border-brand-200 text-warm-700 transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-warm-200 flex items-center justify-center text-xs font-bold text-warm-600 flex-shrink-0 mt-1">AI</div>
            <div className="bg-white border border-offwhite-300 rounded-2xl rounded-tl-sm px-4 py-3 shadow-soft">
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="w-1.5 h-1.5 bg-warm-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 pb-6 pt-3 border-t border-offwhite-200 bg-white">
        <div className="flex items-end gap-2 bg-offwhite-100 border border-offwhite-300 rounded-2xl px-4 py-3 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100 transition-all">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask a question about SIX Group's internal knowledge..."
            rows={1}
            className="flex-1 bg-transparent resize-none text-sm text-warm-900 placeholder:text-warm-400 focus:outline-none max-h-32"
          />
          <Button
            onClick={send}
            disabled={!input.trim() || loading}
            size="sm"
            className="flex-shrink-0 !px-3 !py-2"
          >
            <Send size={14} />
          </Button>
        </div>
        <p className="text-[10px] text-warm-400 mt-1.5 text-center">
          Answers are grounded in internal documents. Always verify with your supervisor.
        </p>
      </div>
    </div>
  )
}
