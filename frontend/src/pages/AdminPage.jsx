import React, { useEffect, useState } from 'react'
import { Users, RefreshCw, Trash2, Plus, Activity, Cpu, ShieldAlert } from 'lucide-react'
import { admin as adminApi } from '../api/client'
import Card, { CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { Input, Select } from '../components/ui/Input'
import PageHeader from '../components/ui/PageHeader'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import ActivityLine from '../components/charts/ActivityLine'
import clsx from 'clsx'

const ROLES    = ['user', 'expert', 'admin']
const DOMAINS  = ['Legal', 'Customer Service', 'HR', 'Finance', 'Technology', 'Operations', 'Marketing', 'Other']
const ROLE_CLR = { admin: 'red', expert: 'blue', user: 'gray' }

const MODELS = ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-8']

function UserRow({ user, onSave }) {
  const [role, setRole]     = useState(user.role)
  const [domain, setDomain] = useState(user.domain || '')
  const [saving, setSaving] = useState(false)
  const dirty = role !== user.role || domain !== (user.domain || '')

  const save = async () => {
    setSaving(true)
    await adminApi.updateUser(user.user_id, { role, domain }).catch(() => null)
    onSave?.()
    setSaving(false)
  }

  return (
    <tr className="border-b border-offwhite-100 hover:bg-offwhite-50 transition-all">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center text-xs font-bold text-brand-600 flex-shrink-0">
            {user.name?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div>
            <p className="text-xs font-medium text-warm-900">{user.name}</p>
            <p className="text-[10px] text-warm-400">{user.email}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="text-xs rounded-lg border border-offwhite-300 bg-white px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-400"
        >
          {ROLES.map((r) => <option key={r}>{r}</option>)}
        </select>
      </td>
      <td className="px-4 py-3">
        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="text-xs rounded-lg border border-offwhite-300 bg-white px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-400"
        >
          <option value="">—</option>
          {DOMAINS.map((d) => <option key={d}>{d}</option>)}
        </select>
      </td>
      <td className="px-4 py-3">
        {dirty && (
          <Button size="xs" onClick={save} loading={saving}>Save</Button>
        )}
      </td>
    </tr>
  )
}

function CreateUserModal({ open, onClose, onCreated }) {
  const [form, setForm]   = useState({ name: '', email: '', password: '', role: 'user', domain: '' })
  const [loading, setLoading] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    setLoading(true)
    try {
      await adminApi.createUser(form)
      onCreated?.()
      onClose()
      setForm({ name: '', email: '', password: '', role: 'user', domain: '' })
    } catch { } finally { setLoading(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create user">
      <div className="space-y-3">
        <Input label="Full name" value={form.name} onChange={set('name')} placeholder="Jane Doe" />
        <Input label="Email" type="email" value={form.email} onChange={set('email')} placeholder="jane@six.ch" />
        <Input label="Password" type="password" value={form.password} onChange={set('password')} placeholder="••••••••" />
        <Select label="Role" value={form.role} onChange={set('role')}>
          {ROLES.map((r) => <option key={r}>{r}</option>)}
        </Select>
        <Select label="Domain" value={form.domain} onChange={set('domain')}>
          <option value="">—</option>
          {DOMAINS.map((d) => <option key={d}>{d}</option>)}
        </Select>
        <div className="flex gap-2 justify-end pt-1">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={loading} disabled={!form.name || !form.email || !form.password}>Create</Button>
        </div>
      </div>
    </Modal>
  )
}

function ModelConfig() {
  const [cfg, setCfg]       = useState(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm]     = useState({ provider: 'gemini', anthropic_api_key: '', anthropic_model: 'claude-haiku-4-5-20251001' })

  useEffect(() => {
    adminApi.getModel().then((c) => {
      setCfg(c)
      setForm((f) => ({ ...f, provider: c.provider, anthropic_model: c.anthropic_model || 'claude-haiku-4-5-20251001' }))
    }).catch(() => null)
  }, [])

  const save = async () => {
    setSaving(true)
    await adminApi.setModel(form).catch(() => null)
    adminApi.getModel().then(setCfg).catch(() => null)
    setSaving(false)
  }

  return (
    <Card>
      <CardHeader title="Model configuration" description="Switch LLM provider at runtime" />
      <div className="space-y-3">
        <Select label="Provider" value={form.provider} onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}>
          {['gemini', 'ollama', 'anthropic'].map((p) => <option key={p}>{p}</option>)}
        </Select>

        {form.provider === 'anthropic' && (
          <>
            <Input label="Anthropic API key" type="password" value={form.anthropic_api_key}
              onChange={(e) => setForm((f) => ({ ...f, anthropic_api_key: e.target.value }))}
              placeholder={cfg?.anthropic_key_set ? '(key already set — leave blank to keep)' : 'sk-ant-…'}
            />
            <Select label="Model" value={form.anthropic_model} onChange={(e) => setForm((f) => ({ ...f, anthropic_model: e.target.value }))}>
              {MODELS.map((m) => <option key={m}>{m}</option>)}
            </Select>
          </>
        )}

        <Button onClick={save} loading={saving} icon={Cpu}>Apply</Button>

        {cfg && (
          <p className="text-[10px] text-warm-400">
            Active: <span className="font-medium text-warm-700">{cfg.provider}</span>
            {cfg.anthropic_model && ` · ${cfg.anthropic_model}`}
          </p>
        )}
      </div>
    </Card>
  )
}

export default function AdminPage() {
  const [users, setUsers]     = useState([])
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [tab, setTab]         = useState('users')

  const loadAll = () => {
    setLoading(true)
    Promise.all([
      adminApi.users().then(setUsers).catch(() => []),
      adminApi.activity().then((a) => {
        // Build daily counts for chart
        const map = (a || []).reduce((acc, e) => {
          const d = (e.timestamp || '').slice(0, 10)
          if (d) acc[d] = (acc[d] || 0) + 1
          return acc
        }, {})
        setActivity(Object.entries(map).sort(([a], [b]) => a.localeCompare(b)).slice(-14).map(([date, count]) => ({ date: date.slice(5), count })))
      }).catch(() => []),
    ]).finally(() => setLoading(false))
  }

  useEffect(loadAll, [])

  const clearKB = async () => {
    if (!confirm('Clear ALL indexed content? This cannot be undone.')) return
    setClearing(true)
    await adminApi.clearKB().catch(() => null)
    setClearing(false)
  }

  return (
    <div className="p-6 space-y-5">
      <PageHeader
        icon={ShieldAlert}
        title="Administration"
        description="User management, model config, and KB controls"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={RefreshCw} onClick={loadAll} loading={loading}>Refresh</Button>
            <Button size="sm" icon={Plus} onClick={() => setAddOpen(true)}>Add user</Button>
          </div>
        }
      />

      {/* Activity chart */}
      <Card>
        <CardHeader title="Activity" description="Queries + ingestions (last 14 days)" />
        <ActivityLine data={activity} />
      </Card>

      {/* Tabs */}
      <div className="flex gap-1 bg-offwhite-200 p-1 rounded-xl w-fit">
        {[['users', Users, 'Users'], ['model', Cpu, 'Model'], ['danger', Trash2, 'Danger']].map(([id, Icon, label]) => (
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

      {tab === 'users' && (
        <Card padding={false}>
          <CardHeader title={`${users.length} users`} className="px-5 pt-5" />
          {users.length === 0 ? (
            <EmptyState icon={Users} title="No users found" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-offwhite-200">
                    {['User', 'Role', 'Domain', ''].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-[10px] font-semibold text-warm-400 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => <UserRow key={u.user_id} user={u} onSave={loadAll} />)}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === 'model' && <ModelConfig />}

      {tab === 'danger' && (
        <Card>
          <CardHeader title="Danger zone" description="Irreversible actions" />
          <div className="bg-brand-50 border border-brand-200 rounded-xl p-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-warm-900">Clear knowledge base</p>
              <p className="text-xs text-warm-500">Permanently delete all indexed chunks. Documents on disk are not affected.</p>
            </div>
            <Button variant="danger" size="sm" icon={Trash2} onClick={clearKB} loading={clearing}>
              Clear KB
            </Button>
          </div>
        </Card>
      )}

      <CreateUserModal open={addOpen} onClose={() => setAddOpen(false)} onCreated={loadAll} />
    </div>
  )
}
