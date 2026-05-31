import React, { useEffect, useRef, useState } from 'react'
import { Ticket, RefreshCw, Plus, CheckCircle, Clock, AlertTriangle, BookOpen, ChevronRight, Star, Upload, FileText, MessageSquarePlus, CloudUpload } from 'lucide-react'
import { tickets as ticketApi, training as trainingApi, ingest as ingestApi } from '../api/client'
import { useAuth, isAdmin } from '../context/AuthContext'
import Card, { CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { Select, Textarea } from '../components/ui/Input'
import PageHeader from '../components/ui/PageHeader'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import clsx from 'clsx'

const DOMAINS  = ['Legal', 'Customer Service', 'HR', 'Finance', 'Technology', 'Operations', 'Marketing', 'Other']
const ACCESS   = ['public', 'internal', 'confidential', 'restricted']
const ACCEPT   = '.pdf,.vtt,.json,.html,.htm'

const STATUS_COLOR = { open: 'orange', resolved: 'green', pending: 'blue' }
const STATUS_ICON  = { open: AlertTriangle, resolved: CheckCircle, pending: Clock }
const DIFF_COLOR   = { easy: 'green', medium: 'yellow', hard: 'red' }

const StatusBanner = ({ msg }) => (
  <div className={clsx('text-xs px-3 py-2 rounded-xl border', msg.startsWith('Error')
    ? 'bg-brand-50 border-brand-200 text-brand-700'
    : 'bg-emerald-50 border-emerald-200 text-emerald-700')}>
    {msg}
  </div>
)

// ── Ticket detail modal ───────────────────────────────────────────────────────
function TicketModal({ ticket, onClose, onUpdate, onRefresh }) {
  const fileRef = useRef(null)
  const [tab, setTab]         = useState('reply')
  const [saving, setSaving]   = useState(false)
  const [success, setSuccess] = useState('')

  // Reset to Write-answer tab whenever a new ticket is opened
  useEffect(() => {
    if (ticket) {
      setTab('reply')
      setSuccess('')
      setReplyText('')
      setFile(null)
    }
  }, [ticket?.ticket_id])

  // Text reply state
  const [replyText, setReplyText] = useState('')
  const [replyDomain, setReplyDomain] = useState('')
  const [replyAccess, setReplyAccess] = useState('internal')

  // File upload state
  const [file, setFile]           = useState(null)
  const [fileDomain, setFileDomain] = useState('')
  const [fileAccess, setFileAccess] = useState('internal')
  const [dragging, setDragging]   = useState(false)

  // Pre-fill domain selects when ticket changes
  useEffect(() => {
    setReplyDomain(ticket?.domain || '')
    setFileDomain(ticket?.domain || '')
  }, [ticket?.ticket_id])

  if (!ticket) return null

  const resolve = async () => {
    setSaving(true)
    await onUpdate(ticket.ticket_id, 'resolved')
    setSaving(false)
    onClose()
  }

  const submitText = async () => {
    if (!replyText.trim()) return
    setSaving(true)
    try {
      await ingestApi.text({
        text:         replyText,
        title:        `Answer: ${ticket.query.slice(0, 60)}`,
        domain:       replyDomain || ticket.domain || '',
        access_level: replyAccess,
        ticket_id:    ticket.ticket_id,
      })
      setSuccess('Answer ingested and ticket resolved.')
      onRefresh?.()
    } catch (err) {
      setSuccess(`Error: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const submitFile = async () => {
    if (!file) return
    setSaving(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('domain', fileDomain || ticket.domain || '')
      fd.append('access_level', fileAccess)
      fd.append('ticket_id', ticket.ticket_id)
      await ingestApi.file(fd)
      // File ingest now auto-resolves via ticket_id on backend
      setSuccess(`"${file.name}" ingested and ticket resolved.`)
      setFile(null)
      onRefresh?.()
    } catch (err) {
      setSuccess(`Error: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  return (
    <Modal open={!!ticket} onClose={onClose} title="Ticket detail" size="lg">
      <div className="space-y-4">

        {/* ── Always-visible details ── */}
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-semibold text-warm-900 leading-snug flex-1">{ticket.query}</p>
          <Badge variant={STATUS_COLOR[ticket.status] || 'gray'}>{ticket.status}</Badge>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-offwhite-100 rounded-xl p-3">
            <p className="text-[10px] text-warm-400 uppercase tracking-wide mb-0.5">Domain</p>
            <p className="text-xs font-medium text-warm-800">{ticket.domain || 'General'}</p>
          </div>
          <div className="bg-offwhite-100 rounded-xl p-3">
            <p className="text-[10px] text-warm-400 uppercase tracking-wide mb-0.5">Reported</p>
            <p className="text-xs font-medium text-warm-800">
              {ticket.created_at ? new Date(ticket.created_at).toLocaleDateString() : '—'}
            </p>
          </div>
        </div>

        {ticket.count > 1 && (
          <div className="bg-brand-50 border border-brand-200 rounded-xl p-3">
            <p className="text-xs text-brand-700 font-medium">
              Asked <span className="font-bold">{ticket.count}×</span> — high-priority knowledge gap
            </p>
          </div>
        )}

        {/* ── Divider + reply toggle (only when open) ── */}
        {ticket.status !== 'resolved' && (
          <>
            <div className="border-t border-offwhite-200" />

            {/* Toggle */}
            <div className="flex gap-1 bg-offwhite-100 p-1 rounded-xl">
              {[
                { id: 'reply',  label: 'Write answer',    icon: MessageSquarePlus },
                { id: 'upload', label: 'Upload document',  icon: Upload },
              ].map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => { setTab(id); setSuccess('') }}
                  className={clsx('flex items-center gap-1.5 flex-1 justify-center px-3 py-2 rounded-lg text-xs font-medium transition-all',
                    tab === id ? 'bg-white text-warm-900 shadow-soft' : 'text-warm-500 hover:text-warm-700'
                  )}>
                  <Icon size={12} />{label}
                </button>
              ))}
            </div>

            {/* ── Write answer ── */}
            {tab === 'reply' && (
              <div className="space-y-3">
                <Textarea
                  label="Your answer"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type the answer here — it will be ingested as a new KB chunk and the ticket auto-resolved."
                  rows={6}
                />
                <div className="grid grid-cols-2 gap-3">
                  <Select label="Domain" value={replyDomain} onChange={(e) => setReplyDomain(e.target.value)}>
                    <option value="">— auto —</option>
                    {DOMAINS.map((d) => <option key={d}>{d}</option>)}
                  </Select>
                  <Select label="Access level" value={replyAccess} onChange={(e) => setReplyAccess(e.target.value)}>
                    {ACCESS.map((a) => <option key={a}>{a}</option>)}
                  </Select>
                </div>
                {success && <StatusBanner msg={success} />}
                <div className="flex gap-2 justify-end">
                  <Button variant="secondary" onClick={onClose}>Cancel</Button>
                  <Button onClick={submitText} loading={saving} disabled={!replyText.trim()} icon={CheckCircle}>
                    Ingest &amp; resolve
                  </Button>
                </div>
              </div>
            )}

            {/* ── Upload document ── */}
            {tab === 'upload' && (
              <div className="space-y-3">
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  onClick={() => !file && fileRef.current?.click()}
                  className={clsx(
                    'border-2 border-dashed rounded-xl p-6 text-center transition-all',
                    file    ? 'border-emerald-300 bg-emerald-50 cursor-default' :
                    dragging? 'border-brand-400 bg-brand-50 cursor-copy' :
                              'border-offwhite-300 hover:border-brand-300 hover:bg-offwhite-50 cursor-pointer'
                  )}
                >
                  {file ? (
                    <div className="flex items-center justify-between gap-3 text-left">
                      <div className="flex items-center gap-2">
                        <FileText size={16} className="text-emerald-500 flex-shrink-0" />
                        <div>
                          <p className="text-xs font-medium text-warm-900">{file.name}</p>
                          <p className="text-[10px] text-warm-400">{(file.size / 1024).toFixed(0)} KB</p>
                        </div>
                      </div>
                      <button onClick={(e) => { e.stopPropagation(); setFile(null) }}
                        className="text-warm-400 hover:text-brand-500 text-xs">Remove</button>
                    </div>
                  ) : (
                    <>
                      <CloudUpload size={24} className={clsx('mx-auto mb-2', dragging ? 'text-brand-400' : 'text-warm-300')} />
                      <p className="text-xs font-medium text-warm-700">Drop file here or click to browse</p>
                      <p className="text-[10px] text-warm-400 mt-0.5">PDF, VTT, JSON, HTML</p>
                    </>
                  )}
                  <input ref={fileRef} type="file" accept={ACCEPT} className="hidden"
                    onChange={(e) => e.target.files[0] && setFile(e.target.files[0])} />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Select label="Domain" value={fileDomain} onChange={(e) => setFileDomain(e.target.value)}>
                    <option value="">— auto —</option>
                    {DOMAINS.map((d) => <option key={d}>{d}</option>)}
                  </Select>
                  <Select label="Access level" value={fileAccess} onChange={(e) => setFileAccess(e.target.value)}>
                    {ACCESS.map((a) => <option key={a}>{a}</option>)}
                  </Select>
                </div>
                {success && <StatusBanner msg={success} />}
                <div className="flex gap-2 justify-end">
                  <Button variant="secondary" onClick={onClose}>Cancel</Button>
                  <Button onClick={submitFile} loading={saving} disabled={!file} icon={Upload}>
                    Upload &amp; resolve
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Resolved state — just a close button */}
        {ticket.status === 'resolved' && (
          <div className="flex justify-end">
            <Button variant="secondary" onClick={onClose}>Close</Button>
          </div>
        )}
      </div>
    </Modal>
  )
}

// ── Ticket card ───────────────────────────────────────────────────────────────
function TicketCard({ ticket, onClick }) {
  const Icon = STATUS_ICON[ticket.status] || Clock
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white border border-offwhite-200 rounded-xl p-4 space-y-2 shadow-soft hover:border-brand-300 hover:shadow-card transition-all group cursor-pointer"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-warm-900 flex-1 leading-snug group-hover:text-brand-700 transition-colors">
          {ticket.query}
        </p>
        <Badge variant={STATUS_COLOR[ticket.status] || 'gray'}>{ticket.status}</Badge>
      </div>
      <div className="flex items-center gap-2 text-[10px] text-warm-400">
        <Icon size={10} />
        <span>{ticket.domain || 'General'}</span>
        <span>·</span>
        <span>{ticket.created_at ? new Date(ticket.created_at).toLocaleDateString() : '—'}</span>
        {ticket.count > 1 && (
          <span className="bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded-full font-medium ml-auto">
            ×{ticket.count}
          </span>
        )}
      </div>
      <div className="flex items-center justify-end">
        <span className="text-[10px] text-warm-300 group-hover:text-brand-400 flex items-center gap-0.5 transition-colors">
          View detail <ChevronRight size={10} />
        </span>
      </div>
    </button>
  )
}

// ── Question detail modal ─────────────────────────────────────────────────────
function QuestionModal({ question, onClose, onDelete, canDelete }) {
  const [deleting, setDeleting] = useState(false)
  if (!question) return null

  const del = async () => {
    setDeleting(true)
    await onDelete(question.question_id)
    setDeleting(false)
    onClose()
  }

  return (
    <Modal open={!!question} onClose={onClose} title="Training question" size="lg">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant={DIFF_COLOR[question.difficulty] || 'gray'}>{question.difficulty}</Badge>
          <Badge variant="blue">{question.domain}</Badge>
        </div>

        <div className="bg-offwhite-100 rounded-xl p-4 border border-offwhite-300">
          <p className="text-[10px] text-warm-400 uppercase tracking-wide mb-1.5">Situation / scenario</p>
          <p className="text-sm text-warm-800 leading-relaxed">{question.situation}</p>
        </div>

        {question.expected_answer && (
          <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-200">
            <p className="text-[10px] text-emerald-600 uppercase tracking-wide mb-1.5 font-semibold">Expected answer</p>
            <p className="text-sm text-warm-800 leading-relaxed">{question.expected_answer}</p>
          </div>
        )}

        <div className="flex items-center justify-between pt-1">
          {canDelete ? (
            <Button variant="danger" size="sm" onClick={del} loading={deleting}>Delete question</Button>
          ) : <span />}
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── QuestionForm ──────────────────────────────────────────────────────────────
function QuestionForm({ onCreated }) {
  const [open, setOpen]       = useState(false)
  const [form, setForm]       = useState({ situation: '', expected_answer: '', domain: 'General', difficulty: 'medium' })
  const [loading, setLoading] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    setLoading(true)
    try {
      await trainingApi.create(form)
      setOpen(false)
      setForm({ situation: '', expected_answer: '', domain: 'General', difficulty: 'medium' })
      onCreated?.()
    } catch { } finally { setLoading(false) }
  }

  return (
    <>
      <Button size="sm" icon={Plus} onClick={() => setOpen(true)}>New question</Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Create training question" size="lg">
        <div className="space-y-3">
          <Textarea label="Situation / scenario" value={form.situation} onChange={set('situation')} rows={3} />
          <Textarea label="Expected answer" value={form.expected_answer} onChange={set('expected_answer')} rows={4} />
          <div className="grid grid-cols-2 gap-3">
            <Select label="Domain" value={form.domain} onChange={set('domain')}>
              {['Legal','Customer Service','HR','Finance','Technology','Operations','Marketing','General'].map((d) => <option key={d}>{d}</option>)}
            </Select>
            <Select label="Difficulty" value={form.difficulty} onChange={set('difficulty')}>
              {['easy','medium','hard'].map((d) => <option key={d}>{d}</option>)}
            </Select>
          </div>
          <div className="flex gap-2 justify-end pt-1">
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={submit} loading={loading} disabled={!form.situation.trim()}>Create</Button>
          </div>
        </div>
      </Modal>
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function TicketsPage() {
  const { user }                      = useAuth()
  const [tickets, setTickets]         = useState([])
  const [questions, setQuestions]     = useState([])
  const [tab, setTab]                 = useState('tickets')
  const [loading, setLoading]         = useState(true)
  const [activeTicket, setActiveTicket]     = useState(null)
  const [activeQuestion, setActiveQuestion] = useState(null)

  const loadTickets   = () => ticketApi.list().then(setTickets).catch(() => setTickets([]))
  const loadQuestions = () => trainingApi.questions(true).then(setQuestions).catch(() => setQuestions([]))

  const load = () => {
    setLoading(true)
    Promise.all([loadTickets(), loadQuestions()]).finally(() => setLoading(false))
  }

  useEffect(load, [])

  const updateTicket = async (id, status) => {
    await ticketApi.update(id, { status }).catch(() => null)
    loadTickets()
  }

  const deleteQuestion = async (id) => {
    await trainingApi.delete(id).catch(() => null)
    loadQuestions()
  }

  return (
    <div className="p-6 space-y-5">
      <PageHeader
        icon={Ticket}
        title="Tickets & Question Bank"
        description="Manage knowledge-gap tickets and training questions"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={RefreshCw} onClick={load}>Refresh</Button>
            {isAdmin(user) && <QuestionForm onCreated={() => loadQuestions()} />}
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 bg-offwhite-200 p-1 rounded-xl w-fit">
        {[['tickets', Ticket, 'Tickets'], ['qbank', BookOpen, 'Question Bank']].map(([id, Icon, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium transition-all',
              tab === id ? 'bg-white text-warm-900 shadow-soft' : 'text-warm-500 hover:text-warm-700'
            )}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tab === 'tickets' ? (
        tickets.length === 0 ? (
          <EmptyState icon={Ticket} title="No tickets" description="Knowledge-gap tickets appear here when users ask unanswered questions" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tickets.map((t) => (
              <TicketCard key={t.ticket_id} ticket={t} onClick={() => setActiveTicket(t)} />
            ))}
          </div>
        )
      ) : (
        <Card padding={false}>
          <CardHeader title={`${questions.length} questions`} className="px-5 pt-5" />
          {questions.length === 0 ? (
            <EmptyState icon={BookOpen} title="No training questions yet" />
          ) : (
            <div className="divide-y divide-offwhite-200">
              {questions.map((q) => (
                <button
                  key={q.question_id}
                  onClick={() => setActiveQuestion(q)}
                  className="w-full text-left flex items-center gap-3 px-5 py-4 hover:bg-offwhite-50 transition-all group cursor-pointer"
                >
                  <Star size={14} className="text-brand-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-warm-900 leading-snug group-hover:text-brand-700 transition-colors">
                      {q.situation?.slice(0, 120)}{q.situation?.length > 120 ? '…' : ''}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant={DIFF_COLOR[q.difficulty] || 'gray'}>{q.difficulty}</Badge>
                      <span className="text-[10px] text-warm-400">{q.domain}</span>
                    </div>
                  </div>
                  <ChevronRight size={14} className="text-warm-300 group-hover:text-brand-400 transition-colors flex-shrink-0" />
                </button>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Modals */}
      <TicketModal
        ticket={activeTicket}
        onClose={() => { setActiveTicket(null); loadTickets() }}
        onUpdate={updateTicket}
        onRefresh={() => { loadTickets(); setActiveTicket(null) }}
      />
      <QuestionModal
        question={activeQuestion}
        onClose={() => setActiveQuestion(null)}
        onDelete={deleteQuestion}
        canDelete={isAdmin(user)}
      />
    </div>
  )
}
