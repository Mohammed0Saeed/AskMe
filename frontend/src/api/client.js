const BASE = '/api'

async function request(method, path, body, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...opts.headers }
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: 'include',
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw Object.assign(new Error(err.error || 'Request failed'), { status: res.status, data: err })
  }
  return res.json()
}

async function upload(path, formData) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw Object.assign(new Error(err.error || 'Upload failed'), { status: res.status, data: err })
  }
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  login:  (email, password) => request('POST', '/auth/login', { email, password }),
  logout: ()                => request('POST', '/auth/logout'),
  me:     ()                => request('GET',  '/auth/me'),
}

// ── Ask ───────────────────────────────────────────────────────────────────────
export const ask = {
  query: (payload) => request('POST', '/ask', payload),
}

// ── Ingest ────────────────────────────────────────────────────────────────────
export const ingest = {
  file: (formData)                  => upload('/ingest', formData),
  text: (body)                      => request('POST', '/ingest/text', body),
}

// ── Audit ─────────────────────────────────────────────────────────────────────
export const audit = {
  list:         (n = 50) => request('GET', `/audit?n=${n}`).then((r) => r.entries ?? r),
  get:          (id)     => request('GET', `/audit/${id}`),
  conversation: (convId) => request('GET', `/conversations/${convId}`).then((r) => r.entries ?? r),
}

// ── Admin ─────────────────────────────────────────────────────────────────────
export const admin = {
  users:       ()       => request('GET',  '/admin/users'),
  updateUser:  (id, b)  => request('PUT',  `/admin/users/${id}`, b),
  createUser:  (b)      => request('POST', '/admin/users', b),
  activity:    ()       => request('GET',  '/admin/activity'),
  clearKB:     ()       => request('POST', '/admin/kb/clear'),
  getModel:    ()       => request('GET',  '/admin/model-config'),
  setModel:    (b)      => request('POST', '/admin/model-config', b),
}

// ── KB ────────────────────────────────────────────────────────────────────────
export const kb = {
  documents: () => request('GET', '/kb/documents'),
  stats:     () => request('GET', '/index/stats'),
  config:    () => request('GET', '/config'),
}

// ── Tickets ───────────────────────────────────────────────────────────────────
export const tickets = {
  list:   ()         => request('GET', '/tickets'),
  update: (id, body) => request('PUT', `/tickets/${id}`, body),
}

// ── Insights ──────────────────────────────────────────────────────────────────
export const insights = {
  stats:  ()    => request('GET',  '/insights'),
  report: (body) => request('POST', '/insights/report', body),
}

// ── Training ──────────────────────────────────────────────────────────────────
export const training = {
  questions: (manage = false) => request('GET', `/training/questions${manage ? '?manage=1' : ''}`).then((r) => r.questions ?? r),
  create:    (body)           => request('POST', '/training/questions', body),
  delete:    (id)             => request('DELETE', `/training/questions/${id}`),
  evaluate:  (body)           => request('POST', '/training/evaluate', body),
  progress:  ()               => request('GET', '/training/progress').then((r) => r.stats ?? r ?? {}),
}
