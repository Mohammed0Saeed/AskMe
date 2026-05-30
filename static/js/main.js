/* ═══════════════════════════════════════════════════════════════
   AskMe — main.js
   Auth-aware: loads current user on boot, gates UI by role.
════════════════════════════════════════════════════════════════ */

let currentUser = null;   // populated by loadCurrentUser() on boot

/* ── Boot sequence ───────────────────────────────────────────── */
(async function boot() {
  await loadCurrentUser();
  applyRoleUI();
  refreshIndexStatus();
  loadProviderBadge();
})();

async function loadCurrentUser() {
  /* Fetches the logged-in user profile.  If the server returns 401 the
     browser is redirected to /login — this catches session expiry too. */
  try {
    const res  = await fetch("/api/auth/me");
    const data = await res.json();
    if (!res.ok) { window.location.href = "/login"; return; }
    currentUser = data;
    renderUserPill(data);
  } catch {
    window.location.href = "/login";
  }
}

function renderUserPill(user) {
  document.getElementById("user-avatar").textContent = user.initials;
  document.getElementById("user-avatar").className   = `user-avatar role-${user.role}`;
  document.getElementById("user-name").textContent   = user.name;
  const badge = document.getElementById("user-role-badge");
  badge.textContent  = user.role.charAt(0).toUpperCase() + user.role.slice(1);
  badge.className    = `user-role-badge role-${user.role}`;
}

function applyRoleUI() {
  /* Gates which tabs are visible and which ingest controls are shown
     based on the logged-in user's role.  Called once after boot. */
  if (!currentUser) return;
  const role = currentUser.role;

  // Ingest tab: hidden for regular users
  const ingestTab = document.getElementById("tab-btn-ingest");
  if (role === "user") {
    ingestTab.classList.add("hidden");
  } else {
    ingestTab.classList.remove("hidden");
  }

  // Admin tab: only for admins
  const adminTab = document.getElementById("tab-btn-admin");
  if (role === "admin") {
    adminTab.classList.remove("hidden");
  }

  // Expert domain lock: show domain notice and lock domain input
  if (role === "expert" && currentUser.domain) {
    const notice = document.getElementById("expert-domain-notice");
    notice.classList.remove("hidden");
    document.getElementById("expert-domain-label").textContent = currentUser.domain;
    // Lock the domain input to their domain
    const domainInput = document.getElementById("domain");
    if (domainInput) {
      domainInput.value    = currentUser.domain;
      domainInput.readOnly = true;
      domainInput.style.background = "#f0fdf4";
    }
    // Hide the auto-detect button since domain is fixed
    const autoBtn = document.getElementById("auto-btn");
    if (autoBtn) autoBtn.style.display = "none";
  }

  // Default tab: ask tab for users/experts, ask tab for admin too
  // (ingest starts hidden for users so the ask tab is already active)
}

/* ── Logout ──────────────────────────────────────────────────── */
document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
});

/* ── Tab switching ───────────────────────────────────────────── */
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b  => b.classList.remove("active"));
    document.querySelectorAll(".tab-page").forEach(p => { p.classList.remove("active"); p.classList.add("hidden"); });
    btn.classList.add("active");
    const page = document.getElementById("tab-" + target);
    page.classList.remove("hidden");
    page.classList.add("active");
    if (target === "audit") loadAuditLog();
    if (target === "admin") loadAdminPanel();
  });
});

/* ── Provider badge + index status ──────────────────────────── */
const indexStatus   = document.getElementById("index-status");
const providerBadge = document.getElementById("provider-badge");

async function refreshIndexStatus() {
  try {
    const d = await (await fetch("/api/index/stats")).json();
    const n = d.total_chunks || 0;
    indexStatus.textContent = n > 0 ? `${n} chunks indexed` : "Index empty";
    indexStatus.classList.toggle("has-data", n > 0);
  } catch { indexStatus.textContent = "—"; }
}

async function loadProviderBadge() {
  try {
    const d = await (await fetch("/api/config")).json();
    providerBadge.textContent = d.label || d.provider;
    providerBadge.classList.toggle("local",  d.provider === "ollama");
    providerBadge.classList.toggle("gemini", d.provider === "gemini");
    if (tokenModelName) tokenModelName.textContent = d.model || d.provider;
  } catch { providerBadge.textContent = "—"; }
}


/* ═══════════════════════════════════════════════════════════════
   TOKEN COUNTER
════════════════════════════════════════════════════════════════ */
let sessionQueries = 0;
let sessionTokens  = 0;

const barPrompt      = document.getElementById("bar-prompt");
const barCompletion  = document.getElementById("bar-completion");
const cntPrompt      = document.getElementById("cnt-prompt");
const cntCompletion  = document.getElementById("cnt-completion");
const cntTotal       = document.getElementById("cnt-total");
const cntEstimated   = document.getElementById("cnt-estimated");
const sessQueries    = document.getElementById("sess-queries");
const sessTotal      = document.getElementById("sess-total");
const sessAvg        = document.getElementById("sess-avg");
const tokenModelName = document.getElementById("token-model-name");

function updateTokenCounter(usage, model) {
  if (!usage) return;
  const p = usage.prompt_tokens, c = usage.completion_tokens, t = usage.total_tokens;
  const maxBar = Math.max(p, c, 1);
  barPrompt.style.width     = `${(p / maxBar * 100).toFixed(1)}%`;
  barCompletion.style.width = `${(c / maxBar * 100).toFixed(1)}%`;
  cntPrompt.textContent     = p.toLocaleString();
  cntCompletion.textContent = c.toLocaleString();
  cntTotal.textContent      = t.toLocaleString();
  cntEstimated.classList.toggle("hidden", !usage.estimated);
  sessionQueries += 1; sessionTokens += t;
  sessQueries.textContent = sessionQueries;
  sessTotal.textContent   = sessionTokens.toLocaleString();
  sessAvg.textContent     = Math.round(sessionTokens / sessionQueries).toLocaleString();
  if (model) tokenModelName.textContent = model;
}


/* ═══════════════════════════════════════════════════════════════
   TAB 1 — INGEST
════════════════════════════════════════════════════════════════ */
const form          = document.getElementById("ingest-form");
const sourceSelect  = document.getElementById("source_type");
const teamsFields   = document.getElementById("teams-fields");
const dropzone      = document.getElementById("dropzone");
const fileInput     = document.getElementById("file");
const dropzoneHint  = document.getElementById("dropzone-hint");
const submitBtn     = document.getElementById("submit-btn");
const btnLabel      = document.getElementById("btn-label");
const btnSpinner    = document.getElementById("btn-spinner");
const ingestPlaceholder = document.getElementById("ingest-placeholder");
const ingestError   = document.getElementById("ingest-error");
const chunksList    = document.getElementById("chunks-list");
const ingestHeader  = document.getElementById("ingest-results-header");
const statsBar      = document.getElementById("stats-bar");
const autoBtn       = document.getElementById("auto-btn");
const domainInput   = document.getElementById("domain");

if (sourceSelect) sourceSelect.addEventListener("change", () =>
  teamsFields.classList.toggle("hidden", sourceSelect.value !== "teams"));

if (autoBtn) autoBtn.addEventListener("click", () => {
  if (currentUser?.role === "expert") return;  // experts can't toggle auto
  const active = autoBtn.classList.toggle("active");
  domainInput.value    = "";
  domainInput.disabled = active;
  domainInput.placeholder = active ? "Gemini will detect automatically" : "e.g. Legal, Finance, HR…";
});

if (dropzone) {
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover",  e => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", ()  => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", e => {
    e.preventDefault(); dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; showFileName(e.dataTransfer.files[0].name); }
  });
  fileInput.addEventListener("change", () => { if (fileInput.files.length) showFileName(fileInput.files[0].name); });
}

function showFileName(name) {
  dropzone.classList.add("has-file");
  dropzoneHint.innerHTML = `<span class="dropzone-filename">&#10003; ${escapeHtml(name)}</span>`;
  document.getElementById("dropzone-accepted").style.display = "none";
}

if (form) form.addEventListener("submit", async e => {
  e.preventDefault();
  ingestError.classList.add("hidden");
  setIngestLoading(true);
  const data = new FormData(form);
  if (autoBtn?.classList.contains("active")) data.set("domain", "");
  try {
    const res  = await fetch("/api/ingest", { method: "POST", body: data });
    const json = await res.json();
    if (!res.ok || json.error) { showIngestError(json.error || `Error ${res.status}`); return; }
    renderIngestResults(json);
    refreshIndexStatus();
  } catch { showIngestError("Network error — is the server running?"); }
  finally   { setIngestLoading(false); }
});

function renderIngestResults(data) {
  ingestPlaceholder.style.display = "none";
  ingestHeader.classList.remove("hidden");
  chunksList.innerHTML = "";
  const domains = [...new Set(data.chunks.map(c => c.metadata.domain).filter(Boolean))];
  const systems = [...new Set(data.chunks.map(c => c.metadata.source_system))];
  statsBar.innerHTML = [
    pill(`${data.total_chunks} chunks`), pill(`+${data.newly_indexed} indexed`),
    ...domains.map(d => pill(d)), ...systems.map(s => pill(s)),
  ].join("");
  data.chunks.forEach((c, i) => chunksList.appendChild(buildChunkCard(c, i + 1)));
}
function setIngestLoading(on) {
  submitBtn.disabled   = on;
  btnLabel.textContent = on ? "Ingesting…" : "Ingest Document";
  btnSpinner.classList.toggle("hidden", !on);
}
function showIngestError(msg) {
  ingestError.textContent = "Error: " + msg; ingestError.classList.remove("hidden");
}


/* ═══════════════════════════════════════════════════════════════
   TAB 2 — ASK
════════════════════════════════════════════════════════════════ */
const askBtn          = document.getElementById("ask-btn");
const askLabel        = document.getElementById("ask-label");
const askSpinner      = document.getElementById("ask-spinner");
const searchQuery     = document.getElementById("search-query");
const askPlaceholder  = document.getElementById("ask-placeholder");
const askError        = document.getElementById("ask-error");
const noDataPanel     = document.getElementById("no-data-panel");
const answerPanel     = document.getElementById("answer-panel");
const answerText      = document.getElementById("answer-text");
const citationsSec    = document.getElementById("citations-section");
const confBadge       = document.getElementById("conf-badge");
const confReason      = document.getElementById("conf-reason");
const modelChip       = document.getElementById("model-chip");
const auditChip       = document.getElementById("audit-chip");
const evidenceSec     = document.getElementById("evidence-section");
const evidenceSub     = document.getElementById("evidence-subtitle");
const searchResults   = document.getElementById("search-results");
const confNotice      = document.getElementById("confidential-notice");

searchQuery.addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runAsk(); });
askBtn.addEventListener("click", runAsk);

async function runAsk() {
  const query = searchQuery.value.trim();
  if (!query) return;

  askError.classList.add("hidden");
  answerPanel.classList.add("hidden");
  noDataPanel.classList.add("hidden");
  confNotice.classList.add("hidden");
  evidenceSec.classList.add("hidden");
  askPlaceholder.style.display = "none";
  setAskLoading(true);

  const body = {
    query,
    top_k:         parseInt(document.getElementById("s-topk").value) || 5,
    access_level:  document.getElementById("s-access").value  || null,
    domain_filter: document.getElementById("s-domain").value.trim() || null,
  };

  try {
    const res  = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const json = await res.json();
    if (!res.ok || json.error) { showAskError(json.error || `Error ${res.status}`); return; }
    renderAskResponse(json);
  } catch { showAskError("Network error — is the server running?"); }
  finally   { setAskLoading(false); }
}

function renderAskResponse(data) {
  updateTokenCounter(data.token_usage, data.model);

  if (data.no_data) {
    noDataPanel.classList.remove("hidden");
    if (data.results?.length) renderEvidence(data);
    return;
  }

  // Confidence
  const lvl = (data.confidence?.level || "LOW").toUpperCase();
  confBadge.textContent = lvl + " CONFIDENCE";
  confBadge.className   = `conf-badge conf-${lvl}`;
  confReason.textContent = data.confidence?.reason || "";

  // Model chip
  const isLocal = (data.model || "").startsWith("ollama");
  modelChip.textContent = data.model || "—";
  modelChip.className   = `model-chip${isLocal ? " local" : ""}`;

  // Audit chip
  if (data.audit_id) {
    auditChip.textContent  = `Audit: ${data.audit_id}`;
    auditChip.onclick = () => { document.querySelector('[data-tab="audit"]').click(); loadAuditLog(); };
  } else { auditChip.textContent = ""; }

  // Answer text
  answerText.innerHTML = renderRefTags(escapeHtml(data.answer));

  // Citations
  renderCitations(data.citations || []);

  answerPanel.classList.remove("hidden");

  // Confidential notice (only for user role — backend also enforces this)
  if (data.confidential_notice?.has_restricted) {
    renderConfidentialNotice(data.confidential_notice);
  }

  renderEvidence(data);
}

function renderConfidentialNotice(notice) {
  /* Shows a yellow notice with expert contacts when a regular user receives
     an answer that draws from confidential or restricted documents. */
  const domains   = (notice.domains || []).join(", ");
  document.getElementById("conf-notice-text").textContent =
    `This answer references document(s) classified as confidential in the following domain(s): ${domains}. ` +
    `Please verify the information with the responsible expert before acting on it.`;

  const contactsEl = document.getElementById("conf-notice-contacts");
  contactsEl.innerHTML = (notice.contacts || []).map(c => `
    <div class="conf-notice-contact">
      <span class="conf-notice-domain-tag">${escapeHtml(c.domain)}</span>
      <strong>${escapeHtml(c.name)}</strong>
      <a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a>
    </div>
  `).join("");

  confNotice.classList.remove("hidden");
}

function renderEvidence(data) {
  if (!data.results?.length) return;
  searchResults.innerHTML = "";
  const scores   = data.results.map(r => r.rerank_score);
  const maxScore = Math.max(...scores), minScore = Math.min(...scores);
  data.results.forEach(r => searchResults.appendChild(buildResultCard(r, maxScore, minScore)));
  evidenceSub.textContent = `${data.results.length} chunk${data.results.length !== 1 ? "s" : ""} · top score: ${scores[0].toFixed(3)}`;
  evidenceSec.classList.remove("hidden");
}

function renderCitations(citations) {
  if (!citations.length) { citationsSec.innerHTML = ""; return; }
  let html = `<div class="citations-title">&#128273; References</div>`;
  for (const c of citations) {
    const page  = c.page_number != null ? ` · Page ${c.page_number}` : "";
    const quote = c.relevant_quote ? `<blockquote class="citation-quote">"${escapeHtml(c.relevant_quote)}"</blockquote>` : "";
    html += `
      <div class="citation-item" id="citation-${c.ref_id}">
        <div class="ref-tag"><span class="ref-tag-badge">${escapeHtml(c.ref_id)}</span></div>
        <div class="citation-meta">
          <strong>${escapeHtml(c.source_file)}</strong>
          ${page ? `<span class="citation-sep">·</span><span>${page.replace(' · ','')}</span>` : ""}
          <span class="citation-sep">·</span>
          <span class="badge badge-domain">${escapeHtml(c.domain)}</span>
          <span class="badge badge-${c.access_level}">${escapeHtml(c.access_level)}</span>
          <span class="citation-sep">·</span>
          <span>&#128100; ${escapeHtml(c.author || "—")}</span>
        </div>
        ${quote}
      </div>`;
  }
  citationsSec.innerHTML = html;
}

function highlightCitation(refId) {
  document.querySelectorAll(".citation-item").forEach(el => el.classList.remove("highlighted"));
  document.querySelectorAll(".ref-badge").forEach(el => el.classList.remove("highlighted"));
  const target = document.getElementById(`citation-${refId}`);
  if (target) { target.classList.add("highlighted"); target.scrollIntoView({ behavior: "smooth", block: "center" }); }
  document.querySelectorAll(`.ref-badge[href="#citation-${refId}"]`).forEach(b => b.classList.add("highlighted"));
  setTimeout(() => {
    if (target) target.classList.remove("highlighted");
    document.querySelectorAll(".ref-badge").forEach(b => b.classList.remove("highlighted"));
  }, 2500);
}

function setAskLoading(on) { askBtn.disabled = on; askLabel.textContent = on ? "Thinking…" : "Ask"; askSpinner.classList.toggle("hidden", !on); }
function showAskError(msg) { askError.textContent = "Error: " + msg; askError.classList.remove("hidden"); }


/* ═══════════════════════════════════════════════════════════════
   TAB 3 — AUDIT LOG
════════════════════════════════════════════════════════════════ */
document.getElementById("refresh-audit-btn").addEventListener("click", loadAuditLog);

async function loadAuditLog() {
  const list = document.getElementById("audit-list");
  list.innerHTML = `<div class="placeholder"><div class="placeholder-icon">&#8987;</div><p>Loading…</p></div>`;
  try {
    const data = await (await fetch("/api/audit?n=30")).json();
    if (!data.entries?.length) {
      list.innerHTML = `<div class="placeholder"><div class="placeholder-icon">&#128196;</div><p>No audit entries yet.</p></div>`;
      return;
    }
    list.innerHTML = "";
    data.entries.forEach(e => list.appendChild(buildAuditEntry(e)));
  } catch { list.innerHTML = `<div class="error-box">Failed to load audit log.</div>`; }
}

function buildAuditEntry(e) {
  const div = document.createElement("div");
  div.className = "audit-entry";
  const ts   = e.timestamp ? new Date(e.timestamp).toLocaleString() : "—";
  const conf = (e.confidence?.level || "LOW").toUpperCase();
  const nCit = (e.citations || []).length;
  div.innerHTML = `
    <div class="audit-entry-header">
      <span class="audit-id">&#9670; ${escapeHtml(e.audit_id)}</span>
      <span class="audit-ts">&#128197; ${ts}</span>
      <span class="conf-badge conf-${conf}" style="font-size:10px">${conf}</span>
    </div>
    <div class="audit-entry-body">
      <div class="audit-query">&#9906; ${escapeHtml(e.query || "")}</div>
      <div class="audit-answer-preview">${renderRefTags(escapeHtml((e.answer || "").substring(0, 240)))}…</div>
    </div>
    <div class="audit-footer">
      ${pill(`${nCit} citation${nCit !== 1 ? "s" : ""}`)}
      ${pill(`${(e.retrieval_trace || []).length} chunks`)}
      ${pill(e.model || "—")}
      ${e.token_usage ? pill(`${(e.token_usage.total_tokens || 0).toLocaleString()} tokens`) : ""}
    </div>`;
  return div;
}


/* ═══════════════════════════════════════════════════════════════
   TAB 4 — ADMIN
════════════════════════════════════════════════════════════════ */
const ROLES   = ["user", "expert", "admin"];
const DOMAINS = ["", "Legal", "Customer Service", "HR", "Finance", "Technology", "Operations", "Marketing", "Data Procurement", "Other"];

document.getElementById("refresh-activity-btn")?.addEventListener("click", loadActivity);
document.getElementById("add-user-btn")?.addEventListener("click", () => {
  document.getElementById("add-user-form").classList.toggle("hidden");
});
document.getElementById("cancel-new-user-btn")?.addEventListener("click", () => {
  document.getElementById("add-user-form").classList.add("hidden");
});
document.getElementById("save-new-user-btn")?.addEventListener("click", async () => {
  const name   = document.getElementById("new-name").value.trim();
  const email  = document.getElementById("new-email").value.trim();
  const role   = document.getElementById("new-role").value;
  const domain = document.getElementById("new-domain").value.trim();
  if (!name || !email) { alert("Name and email are required."); return; }
  const res = await fetch("/api/admin/users", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, role, domain }),
  });
  if (res.ok) { document.getElementById("add-user-form").classList.add("hidden"); loadUsers(); }
  else { const d = await res.json(); alert(d.error || "Failed to create user."); }
});

async function loadAdminPanel() {
  await Promise.all([loadUsers(), loadActivity()]);
}

async function loadUsers() {
  const res  = await fetch("/api/admin/users");
  if (!res.ok) return;
  const users = await res.json();
  const tbody = document.getElementById("users-tbody");
  tbody.innerHTML = "";
  users.forEach(u => tbody.appendChild(buildUserRow(u)));
}

function buildUserRow(u) {
  /* Each row renders the user's info with inline dropdowns for role and domain.
     Edit/Save/Cancel buttons toggle between view and edit mode without a page reload. */
  const tr = document.createElement("tr");
  tr.id = `user-row-${u.user_id}`;

  const roleOptions   = ROLES.map(r   => `<option value="${r}" ${u.role   === r ? "selected" : ""}>${r.charAt(0).toUpperCase() + r.slice(1)}</option>`).join("");
  const domainOptions = DOMAINS.map(d => `<option value="${d}" ${u.domain === d ? "selected" : ""}>${d || "—"}</option>`).join("");

  tr.innerHTML = `
    <td>
      <div class="user-cell">
        <div class="mini-avatar role-${u.role}">${escapeHtml(u.initials)}</div>
        <span>${escapeHtml(u.name)}</span>
      </div>
    </td>
    <td style="font-family:monospace;font-size:12px">${escapeHtml(u.email)}</td>
    <td>
      <span class="view-mode">${badge(u.role)}</span>
      <select class="edit-mode hidden" data-field="role">${roleOptions}</select>
    </td>
    <td>
      <span class="view-mode">${u.domain ? `<span class="badge badge-domain">${escapeHtml(u.domain)}</span>` : "—"}</span>
      <select class="edit-mode hidden" data-field="domain">${domainOptions}</select>
    </td>
    <td>
      <div class="view-mode" style="display:flex;gap:6px">
        <button class="edit-row-btn" onclick="startEdit('${u.user_id}')">Edit</button>
      </div>
      <div class="edit-mode hidden" style="display:flex;gap:6px">
        <button class="save-row-btn"   onclick="saveUser('${u.user_id}')">Save</button>
        <button class="cancel-row-btn" onclick="cancelEdit('${u.user_id}')">Cancel</button>
      </div>
    </td>`;
  return tr;
}

function badge(role) {
  const cls = `role-${role}`;
  return `<span class="user-role-badge ${cls}">${role.charAt(0).toUpperCase() + role.slice(1)}</span>`;
}

function startEdit(uid) {
  const row = document.getElementById(`user-row-${uid}`);
  row.querySelectorAll(".view-mode").forEach(el => el.classList.add("hidden"));
  row.querySelectorAll(".edit-mode").forEach(el => el.classList.remove("hidden"));
}
function cancelEdit(uid) {
  const row = document.getElementById(`user-row-${uid}`);
  row.querySelectorAll(".view-mode").forEach(el => el.classList.remove("hidden"));
  row.querySelectorAll(".edit-mode").forEach(el => el.classList.add("hidden"));
}
async function saveUser(uid) {
  const row    = document.getElementById(`user-row-${uid}`);
  const role   = row.querySelector('[data-field="role"]').value;
  const domain = row.querySelector('[data-field="domain"]').value;
  const res    = await fetch(`/api/admin/users/${uid}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, domain }),
  });
  if (res.ok) { loadUsers(); }
  else { const d = await res.json(); alert(d.error || "Update failed."); }
}

async function loadActivity() {
  const list = document.getElementById("activity-list");
  if (!list) return;
  try {
    const data = await (await fetch("/api/admin/activity")).json();
    if (!data.length) { list.innerHTML = `<div class="placeholder"><p>No activity yet.</p></div>`; return; }
    list.innerHTML = "";
    data.forEach(u => list.appendChild(buildActivityCard(u)));
  } catch { list.innerHTML = `<div class="error-box">Failed to load activity.</div>`; }
}

function buildActivityCard(u) {
  const div = document.createElement("div");
  div.className = "activity-card";
  const lastTs = u.last_activity ? new Date(u.last_activity).toLocaleString() : "Never";
  div.innerHTML = `
    <div class="activity-avatar role-${u.role} mini-avatar">${escapeHtml(u.initials)}</div>
    <div class="activity-info">
      <div class="activity-name">${escapeHtml(u.name)}</div>
      <div class="activity-email">${escapeHtml(u.email)}</div>
    </div>
    <div class="activity-stats">
      <div class="activity-stat"><strong>${u.queries}</strong> queries</div>
      <div class="activity-stat"><strong>${u.ingests}</strong> ingests</div>
    </div>
    <div class="activity-last">Last: ${lastTs}</div>`;
  return div;
}


/* ═══════════════════════════════════════════════════════════════
   SHARED CARD BUILDERS
════════════════════════════════════════════════════════════════ */
function buildChunkCard(chunk, num) {
  const m = chunk.metadata;
  const div = document.createElement("div");
  div.className = "chunk-card";
  div.innerHTML = `
    <div class="chunk-card-header">
      <span class="chunk-num">Chunk #${num}</span>
      <span class="chunk-id">#${escapeHtml(chunk.chunk_id)}</span>
      <div class="badges">
        ${m.domain        ? `<span class="badge badge-domain">${escapeHtml(m.domain)}</span>` : ""}
        ${m.source_system ? `<span class="badge badge-source">${escapeHtml(m.source_system)}</span>` : ""}
        <span class="badge badge-${m.access_level}">${escapeHtml(m.access_level)}</span>
      </div>
    </div>
    <div class="chunk-card-body">
      <div class="chunk-meta">
        <span>&#128100; <strong>${escapeHtml(m.author || "—")}</strong></span>
        <span>&#128197; <strong>${escapeHtml(m.date   || "—")}</strong></span>
        ${m.page_number != null ? `<span>&#128196; page <strong>${m.page_number}</strong></span>` : ""}
      </div>
      <div class="chunk-text collapsed" id="ic-${num}">${escapeHtml(chunk.content)}</div>
      <button class="expand-btn" data-target="ic-${num}" data-expanded="false">Show more</button>
    </div>`;
  wireExpand(div);
  return div;
}

function buildResultCard(result, maxScore, minScore) {
  const m      = result.chunk.metadata;
  const range  = maxScore - minScore || 1;
  const barPct = 10 + 90 * ((result.rerank_score - minScore) / range);
  const div    = document.createElement("div");
  div.className = "result-card";
  div.innerHTML = `
    <div class="result-card-header">
      <div class="rank-badge ${result.rank <= 3 ? `rank-${result.rank}` : "rank-n"}">#${result.rank}</div>
      <span class="chunk-id">${escapeHtml(result.chunk.chunk_id)}</span>
      <div class="badges">
        ${m.domain        ? `<span class="badge badge-domain">${escapeHtml(m.domain)}</span>` : ""}
        ${m.source_system ? `<span class="badge badge-source">${escapeHtml(m.source_system)}</span>` : ""}
        <span class="badge badge-${m.access_level}">${escapeHtml(m.access_level)}</span>
      </div>
    </div>
    <div class="score-strip">
      <span class="score-label">Re-rank</span>
      <div class="rerank-bar-wrap">
        <div class="rerank-bar-track"><div class="rerank-bar-fill" style="width:${barPct.toFixed(1)}%"></div></div>
        <span class="score-num">${result.rerank_score.toFixed(3)}</span>
      </div>
      <span class="score-chip"><span>Vector</span> ${result.vector_score.toFixed(3)}</span>
      <span class="score-chip"><span>BM25</span>   ${result.bm25_score.toFixed(2)}</span>
      <span class="score-chip"><span>RRF</span>    ${result.rrf_score.toFixed(4)}</span>
    </div>
    <div class="result-card-body">
      <div class="chunk-meta">
        <span>&#128100; <strong>${escapeHtml(m.author || "—")}</strong></span>
        <span>&#128197; <strong>${escapeHtml(m.date   || "—")}</strong></span>
        ${m.page_number != null ? `<span>&#128196; page <strong>${m.page_number}</strong></span>` : ""}
        <span>&#128193; <strong>${escapeHtml(m.source_file || "—")}</strong></span>
      </div>
      <div class="chunk-text collapsed" id="sr-${result.rank}">${escapeHtml(result.chunk.content)}</div>
      <button class="expand-btn" data-target="sr-${result.rank}" data-expanded="false">Show more</button>
    </div>`;
  wireExpand(div);
  return div;
}

function wireExpand(card) {
  card.querySelector(".expand-btn").addEventListener("click", function () {
    const el = document.getElementById(this.dataset.target);
    const expanded = this.dataset.expanded === "true";
    el.classList.toggle("collapsed", expanded);
    this.textContent      = expanded ? "Show more" : "Show less";
    this.dataset.expanded = String(!expanded);
  });
}


/* ── Shared helpers ──────────────────────────────────────────── */
function pill(text) { return `<span class="stat-pill">${escapeHtml(text)}</span>`; }

function renderRefTags(escapedText) {
  return escapedText.replace(/\[REF-(\d+)\]/g, (_, n) =>
    `<a class="ref-badge" href="#citation-REF-${n}" onclick="highlightCitation('REF-${n}');return false;">[REF-${n}]</a>`
  );
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
