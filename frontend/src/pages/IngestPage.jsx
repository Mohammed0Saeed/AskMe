import React, { useRef, useState } from 'react'
import { Upload, FileText, CheckCircle, AlertCircle, CloudUpload } from 'lucide-react'
import { ingest as ingestApi } from '../api/client'
import Card, { CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { Select, Textarea } from '../components/ui/Input'
import PageHeader from '../components/ui/PageHeader'
import clsx from 'clsx'

const DOMAINS = ['Legal', 'Customer Service', 'HR', 'Finance', 'Technology', 'Operations', 'Marketing', 'Data Procurement', 'Other']
const ACCESS  = ['public', 'internal', 'confidential', 'restricted']
const ACCEPT  = '.pdf,.vtt,.json,.html,.htm'

function LogEntry({ entry }) {
  const ok = entry.status === 'success'
  return (
    <div className={clsx(
      'flex items-start gap-3 px-4 py-3 rounded-xl border text-xs',
      ok ? 'bg-emerald-50 border-emerald-200' : 'bg-brand-50 border-brand-200'
    )}>
      {ok
        ? <CheckCircle size={14} className="text-emerald-500 flex-shrink-0 mt-0.5" />
        : <AlertCircle size={14} className="text-brand-500 flex-shrink-0 mt-0.5" />}
      <div className="min-w-0">
        <p className="font-medium text-warm-900 truncate">{entry.filename}</p>
        <p className={ok ? 'text-emerald-600' : 'text-brand-600'}>{entry.message}</p>
      </div>
    </div>
  )
}

export default function IngestPage() {
  const fileRef = useRef(null)
  const [files, setFiles]       = useState([])
  const [domain, setDomain]     = useState('Technology')
  const [access, setAccess]     = useState('internal')
  const [dragging, setDragging] = useState(false)
  const [log, setLog]           = useState([])
  const [loading, setLoading]   = useState(false)

  // Text ingest
  const [textMode, setTextMode]   = useState(false)
  const [textTitle, setTextTitle] = useState('')
  const [textBody, setTextBody]   = useState('')

  const addFiles = (incoming) => {
    const arr = Array.from(incoming).filter((f) => {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      return ACCEPT.includes(ext)
    })
    setFiles((prev) => [...prev, ...arr])
  }

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const removeFile = (i) => setFiles((f) => f.filter((_, idx) => idx !== i))

  const submit = async () => {
    if (textMode) {
      if (!textTitle.trim() || !textBody.trim()) return
      setLoading(true)
      try {
        const res = await ingestApi.text({ title: textTitle, text: textBody, domain, access_level: access })
        setLog((l) => [{ filename: textTitle, status: 'success', message: `${res.chunks_created ?? '?'} chunks created` }, ...l])
        setTextTitle(''); setTextBody('')
      } catch (err) {
        setLog((l) => [{ filename: textTitle, status: 'error', message: err.message }, ...l])
      } finally {
        setLoading(false)
      }
      return
    }

    if (!files.length) return
    setLoading(true)
    const results = []
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('domain', domain)
      fd.append('access_level', access)
      try {
        const res = await ingestApi.file(fd)
        results.push({ filename: file.name, status: 'success', message: `${res.chunks_created ?? '?'} chunks created` })
      } catch (err) {
        results.push({ filename: file.name, status: 'error', message: err.message })
      }
    }
    setLog((l) => [...results, ...l])
    setFiles([])
    setLoading(false)
  }

  return (
    <div className="p-6 space-y-5">
      <PageHeader icon={Upload} title="Ingest Documents" description="Add files or text to the knowledge base" />

      {/* Mode toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setTextMode(false)}
          className={clsx(
            'px-4 py-2 rounded-xl text-sm font-medium transition-all',
            !textMode ? 'bg-brand-500 text-white shadow-soft' : 'bg-white border border-offwhite-300 text-warm-600 hover:bg-offwhite-100'
          )}
        >
          File upload
        </button>
        <button
          onClick={() => setTextMode(true)}
          className={clsx(
            'px-4 py-2 rounded-xl text-sm font-medium transition-all',
            textMode ? 'bg-brand-500 text-white shadow-soft' : 'bg-white border border-offwhite-300 text-warm-600 hover:bg-offwhite-100'
          )}
        >
          Paste text
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Main upload area */}
        <div className="lg:col-span-2 space-y-4">
          {!textMode ? (
            <>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={clsx(
                  'border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all',
                  dragging
                    ? 'border-brand-400 bg-brand-50'
                    : 'border-offwhite-300 hover:border-brand-300 hover:bg-offwhite-50'
                )}
              >
                <CloudUpload size={32} className={clsx('mx-auto mb-3', dragging ? 'text-brand-500' : 'text-warm-300')} />
                <p className="text-sm font-medium text-warm-700">Drop files here or click to browse</p>
                <p className="text-xs text-warm-400 mt-1">PDF, VTT, JSON, HTML · Up to 50 MB each</p>
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept={ACCEPT}
                  className="hidden"
                  onChange={(e) => addFiles(e.target.files)}
                />
              </div>

              {files.length > 0 && (
                <div className="space-y-2">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 bg-white border border-offwhite-300 rounded-xl px-3 py-2">
                      <FileText size={14} className="text-brand-400 flex-shrink-0" />
                      <span className="text-xs text-warm-700 flex-1 truncate">{f.name}</span>
                      <span className="text-[10px] text-warm-400">{(f.size / 1024).toFixed(0)} KB</span>
                      <button onClick={() => removeFile(i)} className="text-warm-400 hover:text-brand-500 transition-all">✕</button>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <Card>
              <div className="space-y-3">
                <input
                  value={textTitle}
                  onChange={(e) => setTextTitle(e.target.value)}
                  placeholder="Document title"
                  className="w-full rounded-xl border border-offwhite-300 bg-white px-3 py-2 text-sm text-warm-900 placeholder:text-warm-400 focus:outline-none focus:ring-2 focus:ring-brand-400"
                />
                <Textarea
                  value={textBody}
                  onChange={(e) => setTextBody(e.target.value)}
                  placeholder="Paste document text here…"
                  rows={12}
                />
              </div>
            </Card>
          )}
        </div>

        {/* Options + submit */}
        <div className="space-y-4">
          <Card>
            <CardHeader title="Options" />
            <div className="space-y-3">
              <Select
                label="Domain"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
              >
                {DOMAINS.map((d) => <option key={d}>{d}</option>)}
              </Select>
              <Select
                label="Access level"
                value={access}
                onChange={(e) => setAccess(e.target.value)}
              >
                {ACCESS.map((a) => <option key={a}>{a}</option>)}
              </Select>
            </div>
          </Card>

          <Button
            onClick={submit}
            loading={loading}
            disabled={textMode ? !textTitle.trim() || !textBody.trim() : !files.length}
            className="w-full justify-center"
          >
            {loading ? 'Ingesting…' : 'Ingest'}
          </Button>
        </div>
      </div>

      {/* Log */}
      {log.length > 0 && (
        <Card>
          <CardHeader title="Ingest log" />
          <div className="space-y-2">
            {log.map((e, i) => <LogEntry key={i} entry={e} />)}
          </div>
        </Card>
      )}
    </div>
  )
}
