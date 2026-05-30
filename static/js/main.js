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

  // Tickets + Insights + KB: experts and admins
  if (role === "expert" || role === "admin") {
    document.getElementById("tab-btn-tickets").classList.remove("hidden");
    document.getElementById("tab-btn-insights").classList.remove("hidden");
    document.getElementById("tab-btn-kb").classList.remove("hidden");
  }

  // Top-K and model info: admins only
  if (role === "admin") {
    document.getElementById("topk-filter")?.classList.remove("hidden");
  }

  // Domain filter in tickets: only admins see it
  if (role === "admin") {
    document.getElementById("ticket-domain-filter").classList.remove("hidden");
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
      domainInput.disabled = true;
      domainInput.style.opacity = ".7";
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
    if (target === "audit")    loadAuditLog();
    if (target === "admin")    loadAdminPanel();
    if (target === "tickets")  loadTickets();
    if (target === "insights") loadInsights();
    if (target === "kb")       loadKBExplorer();
  });
});

/* ── Index status (background keep-alive only) ───────────────── */
async function refreshIndexStatus() {
  try { await fetch("/api/index/stats"); } catch { /* silent */ }
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
   TAB 2 — CHAT
════════════════════════════════════════════════════════════════ */
const askBtn      = document.getElementById("ask-btn");
const askLabel    = document.getElementById("ask-label");
const askSpinner  = document.getElementById("ask-spinner");
const searchQuery = document.getElementById("search-query");
const askError    = document.getElementById("ask-error");

/* Auto-resize textarea */
searchQuery.addEventListener("input", () => {
  searchQuery.style.height = "auto";
  searchQuery.style.height = Math.min(searchQuery.scrollHeight, 160) + "px";
});

/* Enter = send, Shift+Enter = newline */
searchQuery.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runAsk(); }
});
askBtn.addEventListener("click", runAsk);

/* New Chat */
document.getElementById("new-chat-btn")?.addEventListener("click", () => {
  document.getElementById("chat-messages").innerHTML = `
    <div class="chat-welcome" id="chat-welcome">
      <div class="chat-welcome-icon">&#9670;</div>
      <h3 class="chat-welcome-title">How can I help you today?</h3>
      <p class="chat-welcome-hint">Ask anything about your documents. Every answer shows the source file, page, and author for each claim.</p>
    </div>`;
  searchQuery.value = "";
  searchQuery.style.height = "auto";
  askError.classList.add("hidden");
});

async function runAsk() {
  const query = searchQuery.value.trim();
  if (!query || askBtn.disabled) return;

  document.getElementById("chat-welcome")?.remove();
  askError.classList.add("hidden");
  appendUserMessage(query);
  searchQuery.value = "";
  searchQuery.style.height = "auto";
  setAskLoading(true);

  const body = {
    query,
    top_k:         parseInt(document.getElementById("s-topk").value) || 5,
    access_level:  document.getElementById("s-access").value  || null,
    domain_filter: document.getElementById("s-domain").value  || null,
  };

  try {
    const res  = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const json = await res.json();
    if (!res.ok || json.error) { appendAiError(json.error || `Error ${res.status}`); return; }
    appendAiMessage(json);
  } catch { appendAiError("Network error — is the server running?"); }
  finally   { setAskLoading(false); scrollChat(); }
}

function appendUserMessage(text) {
  const div = document.createElement("div");
  div.className = "chat-msg chat-msg-user animate-in";
  div.innerHTML = `<div class="chat-bubble-user">${escapeHtml(text)}</div>`;
  document.getElementById("chat-messages").appendChild(div);
  scrollChat();
}

function appendAiMessage(data) {
  const msgs  = document.getElementById("chat-messages");
  const div   = document.createElement("div");
  div.className = "chat-msg chat-msg-ai animate-in";
  const mid   = "m" + Date.now();

  if (data.no_data) {
    div.innerHTML = `
      <div class="chat-bubble-ai">
        <div class="chat-ai-header">
          <span style="font-size:18px">&#128270;</span>
          <span style="font-weight:700;color:#92400e">Nothing found in the knowledge base</span>
        </div>
        <div class="chat-answer-body" style="color:var(--text-muted)">
          ${escapeHtml(data.answer || "The documents currently indexed do not contain relevant information for this question.")}
        </div>
      </div>`;
  } else {
    const lvl  = (data.confidence?.level || "LOW").toUpperCase();
    const cits = data.citations || [];
    const hasEv = data.results?.length > 0;

    div.innerHTML = `
      <div class="chat-bubble-ai">
        <div class="chat-ai-header">
          <span class="conf-badge conf-${lvl}">${lvl}</span>
          <span class="conf-reason">${escapeHtml(data.confidence?.reason || "")}</span>
          ${currentUser?.role === "admin" && data.audit_id
            ? `<span class="audit-chip" style="cursor:default">${escapeHtml(data.audit_id)}</span>` : ""}
        </div>
        <div class="chat-answer-body">${renderRefTagsScoped(escapeHtml(data.answer), mid)}</div>
        ${cits.length ? buildCitationsHtml(cits, mid) : ""}
        ${data.confidential_notice?.has_restricted ? buildConfNoticeHtml(data.confidential_notice) : ""}
        ${hasEv ? `
          <div class="chat-evidence-toggle" data-target="${mid}-ev" data-open="false">
            &#128269; Show retrieved evidence <span style="font-size:10px">&#9660;</span>
          </div>
          <div class="chat-evidence hidden" id="${mid}-ev">${buildEvidenceHtml(data.results)}</div>` : ""}
      </div>`;

    /* Evidence toggle */
    div.querySelector(".chat-evidence-toggle")?.addEventListener("click", function () {
      const open = this.dataset.open === "true";
      document.getElementById(this.dataset.target).classList.toggle("hidden", open);
      this.dataset.open = String(!open);
      this.querySelector("span:last-child").innerHTML = open ? "&#9660;" : "&#9650;";
    });

    /* Ref-badge → citation highlight within this bubble */
    div.querySelectorAll(".ref-badge[data-ref]").forEach(b => {
      b.addEventListener("click", e => {
        e.preventDefault();
        const el = div.querySelector(`#cit-${mid}-${b.dataset.ref}`);
        if (!el) return;
        div.querySelectorAll(".citation-item").forEach(c => c.classList.remove("highlighted"));
        el.classList.add("highlighted");
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setTimeout(() => el.classList.remove("highlighted"), 2500);
      });
    });
  }

  msgs.appendChild(div);
}

function appendAiError(msg) {
  const div = document.createElement("div");
  div.className = "chat-msg chat-msg-ai animate-in";
  div.innerHTML = `<div class="chat-bubble-ai is-error"><div class="chat-answer-body" style="color:#b91c1c">&#9888; ${escapeHtml(msg)}</div></div>`;
  document.getElementById("chat-messages").appendChild(div);
}

function buildCitationsHtml(citations, mid) {
  let html = `<div class="chat-citations"><div class="citations-title">&#128273; References</div>`;
  for (const c of citations) {
    const page  = c.page_number != null ? `&#128196; Page ${c.page_number}` : "";
    const quote = c.relevant_quote ? `<blockquote class="citation-quote">"${escapeHtml(c.relevant_quote)}"</blockquote>` : "";
    html += `
      <div class="citation-item" id="cit-${mid}-${c.ref_id}">
        <div class="ref-tag"><span class="ref-tag-badge">${escapeHtml(c.ref_id)}</span></div>
        <div class="citation-meta">
          <strong>${escapeHtml(c.source_file)}</strong>
          ${page ? `<span class="citation-sep">·</span><span>${page}</span>` : ""}
          <span class="citation-sep">·</span>
          <span class="badge badge-domain">${escapeHtml(c.domain)}</span>
          <span class="badge badge-${c.access_level}">${escapeHtml(c.access_level)}</span>
          <span class="citation-sep">·</span>
          <span>&#128100; ${escapeHtml(c.author || "—")}</span>
        </div>${quote}
      </div>`;
  }
  return html + "</div>";
}

function buildConfNoticeHtml(notice) {
  const domains   = (notice.domains || []).join(", ");
  const contacts  = (notice.contacts || []).map(c => `
    <div class="conf-notice-contact">
      <span class="conf-notice-domain-tag">${escapeHtml(c.domain)}</span>
      <strong>${escapeHtml(c.name)}</strong>
      <a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a>
    </div>`).join("");
  return `
    <div class="chat-conf-notice">
      <div class="chat-conf-notice-icon">&#128274;</div>
      <div class="chat-conf-notice-body">
        <strong>Confidential source(s) referenced.</strong>
        <p>Domains: ${escapeHtml(domains)}. Verify with the responsible expert before acting on it.</p>
        <div class="conf-notice-contacts">${contacts}</div>
      </div>
    </div>`;
}

function buildEvidenceHtml(results) {
  const scores = results.map(r => r.rerank_score);
  const max = Math.max(...scores), min = Math.min(...scores);
  return results.map(r => {
    const m = r.chunk.metadata;
    const pct = (10 + 90 * ((r.rerank_score - min) / (max - min || 1))).toFixed(1);
    return `
      <div class="result-card">
        <div class="result-card-header">
          <div class="rank-badge ${r.rank <= 3 ? `rank-${r.rank}` : "rank-n"}">#${r.rank}</div>
          <span class="chunk-id">${escapeHtml(r.chunk.chunk_id)}</span>
          <div class="badges">
            ${m.domain ? `<span class="badge badge-domain">${escapeHtml(m.domain)}</span>` : ""}
            <span class="badge badge-${m.access_level}">${escapeHtml(m.access_level)}</span>
          </div>
        </div>
        <div class="score-strip">
          <span class="score-label">Re-rank</span>
          <div class="rerank-bar-wrap">
            <div class="rerank-bar-track"><div class="rerank-bar-fill" style="width:${pct}%"></div></div>
            <span class="score-num">${r.rerank_score.toFixed(3)}</span>
          </div>
          <span class="score-chip"><span>Vector</span> ${r.vector_score.toFixed(3)}</span>
          <span class="score-chip"><span>BM25</span> ${r.bm25_score.toFixed(2)}</span>
        </div>
        <div class="result-card-body">
          <div class="chunk-meta">
            <span>&#128100; <strong>${escapeHtml(m.author || "—")}</strong></span>
            <span>&#128197; <strong>${escapeHtml(m.date || "—")}</strong></span>
            ${m.page_number != null ? `<span>&#128196; page <strong>${m.page_number}</strong></span>` : ""}
            <span>&#128193; <strong>${escapeHtml(m.source_file || "—")}</strong></span>
          </div>
          <div class="chunk-text collapsed">${escapeHtml(r.chunk.content)}</div>
          <button class="expand-btn" onclick="const t=this.previousElementSibling;const c=t.classList.toggle('collapsed');this.textContent=c?'Show more':'Show less'">Show more</button>
        </div>
      </div>`;
  }).join("");
}

function scrollChat() {
  const el = document.getElementById("chat-messages");
  if (el) el.scrollTop = el.scrollHeight;
}

function setAskLoading(on) {
  askBtn.disabled = on;
  askLabel.innerHTML = on ? "" : "&#9658;";
  askSpinner.classList.toggle("hidden", !on);
}

/* Scoped ref-tag renderer — uses data-ref so clicks are per-bubble */
function renderRefTagsScoped(escapedText, mid) {
  return escapedText.replace(/\[REF-(\d+)\]/g, (_, n) =>
    `<a class="ref-badge" href="#" data-ref="REF-${n}" onclick="return false;">[REF-${n}]</a>`
  );
}

/* Legacy global renderRefTags — used by audit log preview */
function renderRefTags(escapedText) {
  return escapedText.replace(/\[REF-(\d+)\]/g, (_, n) => `<span class="ref-badge">[REF-${n}]</span>`);
}


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
    data.entries.forEach((e, i) => list.appendChild(buildAuditEntry(e, i + 1)));
  } catch { list.innerHTML = `<div class="error-box">Failed to load audit log.</div>`; }
}

function buildAuditEntry(e, idx = 1) {
  const div = document.createElement("div");
  div.className = `audit-entry stagger-${Math.min(idx, 10)}`;
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

document.getElementById("clear-kb-btn")?.addEventListener("click", async () => {
  if (!confirm("This will permanently delete all indexed documents. Are you sure?")) return;
  const btn = document.getElementById("clear-kb-btn");
  const fb  = document.getElementById("clear-kb-feedback");
  btn.disabled = true;
  btn.textContent = "Clearing…";
  try {
    const res  = await fetch("/api/admin/kb/clear", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      fb.innerHTML = `<div class="error-box" style="background:#dcfce7;border-color:#bbf7d0;color:#15803d;margin-top:12px">&#10003; ${escapeHtml(data.message)}</div>`;
      refreshIndexStatus();
    } else {
      fb.innerHTML = `<div class="error-box" style="margin-top:12px">${escapeHtml(data.error || "Failed.")}</div>`;
    }
  } catch {
    fb.innerHTML = `<div class="error-box" style="margin-top:12px">Network error.</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = "&#128465; Clear Knowledge Base";
  }
});
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
    data.forEach((u, i) => list.appendChild(buildActivityCard(u, i + 1)));
  } catch { list.innerHTML = `<div class="error-box">Failed to load activity.</div>`; }
}

function buildActivityCard(u, idx = 1) {
  const div = document.createElement("div");
  div.className = `activity-card stagger-${Math.min(idx, 10)}`;
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
  div.className = `chunk-card stagger-${Math.min(num, 10)}`;
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

function buildResultCard(result, maxScore, minScore, idx = 1) {
  const m      = result.chunk.metadata;
  const range  = maxScore - minScore || 1;
  const barPct = 10 + 90 * ((result.rerank_score - minScore) / range);
  const div    = document.createElement("div");
  div.className = `result-card stagger-${Math.min(idx, 10)}`;
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

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}


/* ═══════════════════════════════════════════════════════════════
   TAB 5 — TICKETS
════════════════════════════════════════════════════════════════ */
document.getElementById("refresh-tickets-btn")?.addEventListener("click", loadTickets);
document.getElementById("ticket-domain-filter")?.addEventListener("change", loadTickets);
document.getElementById("ticket-status-filter")?.addEventListener("change", loadTickets);

async function loadTickets() {
  const list = document.getElementById("tickets-list");
  list.innerHTML = `<div class="placeholder"><div class="placeholder-icon">&#8987;</div><p>Loading…</p></div>`;

  const domain = document.getElementById("ticket-domain-filter")?.value || "";
  const status = document.getElementById("ticket-status-filter")?.value || "";
  const url    = "/api/tickets" + (domain ? `?domain=${encodeURIComponent(domain)}` : "");

  try {
    const res  = await fetch(url);
    if (res.status === 403) { list.innerHTML = `<div class="error-box">Access restricted.</div>`; return; }
    let tickets = await res.json();
    if (status) tickets = tickets.filter(t => t.status === status);
    if (!tickets.length) {
      list.innerHTML = `<div class="placeholder"><div class="placeholder-icon">&#127915;</div><p>No tickets found.</p></div>`;
      return;
    }
    list.innerHTML = "";
    tickets.forEach((t, i) => list.appendChild(buildTicketCard(t, i + 1)));
  } catch {
    list.innerHTML = `<div class="error-box">Failed to load tickets.</div>`;
  }
}

function buildTicketCard(t, idx = 1) {
  const div    = document.createElement("div");
  div.className = `ticket-card ${t.status === "resolved" ? "ticket-resolved" : ""} stagger-${Math.min(idx, 10)}`;
  div.id        = `ticket-${t.ticket_id}`;

  const tid     = t.ticket_id;
  const ts      = t.created_at ? new Date(t.created_at).toLocaleString() : "—";
  const isOpen  = t.status === "open";
  const noDataBadge = t.no_data ? `<span class="ticket-nodata-badge">No answer</span>` : "";
  const ACCESS_OPTIONS = ["public","internal","confidential","restricted"]
    .map(v => `<option value="${v}"${v==="internal"?" selected":""}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`)
    .join("");

  div.innerHTML = `
    <div class="ticket-card-header">
      <span class="ticket-id">&#127915; ${escapeHtml(tid)}</span>
      <span class="conf-badge conf-LOW" style="font-size:10px">LOW</span>
      ${noDataBadge}
      <span class="badge badge-domain">${escapeHtml(t.domain)}</span>
      <span class="ticket-status-badge ticket-status-${t.status}">${t.status}</span>
      <span class="ticket-ts">&#128197; ${ts}</span>
    </div>
    <div class="ticket-card-body">
      <div class="ticket-query">&#9906; ${escapeHtml(t.query)}</div>
      <div class="ticket-answer">${escapeHtml((t.answer || "").substring(0, 200))}${(t.answer||"").length > 200 ? "…" : ""}</div>
      ${t.confidence_reason ? `<div class="ticket-reason">&#128270; ${escapeHtml(t.confidence_reason)}</div>` : ""}
    </div>
    <div class="ticket-card-footer">
      ${pill("&#128100; " + escapeHtml(t.user_name))}
      ${t.audit_id ? pill("Audit: " + escapeHtml(t.audit_id)) : ""}
      <div class="ticket-footer-actions">
        ${isOpen ? `<button class="ticket-answer-btn" data-id="${tid}">&#9998; Answer Ticket</button>` : ""}
        <button class="${isOpen ? "ticket-resolve-btn" : "ticket-reopen-btn"}"
                data-id="${tid}" data-status="${isOpen ? "resolved" : "open"}">
          ${isOpen ? "Mark Resolved" : "Reopen"}
        </button>
      </div>
    </div>

    <!-- ── Inline edit panel (open tickets only) ── -->
    ${isOpen ? `
    <div class="ticket-edit-panel hidden" id="tedit-panel-${tid}">
      <div class="tedit-tabs">
        <button class="tedit-tab tedit-tab-active" data-mode="text">&#9998; Write Answer</button>
        <button class="tedit-tab" data-mode="upload">&#8659; Upload Document</button>
      </div>

      <!-- Write answer mode -->
      <div class="tedit-mode" id="tedit-text-${tid}">
        <div class="field-group">
          <label>Answer title</label>
          <input type="text" id="tedit-title-${tid}" value="${escapeHtml(t.query)}" />
        </div>
        <div class="field-group">
          <label>Answer content</label>
          <textarea id="tedit-body-${tid}" rows="5"
                    placeholder="Write the correct answer to add to the knowledge base…"></textarea>
        </div>
        <div class="field-group">
          <label>Access level</label>
          <select id="tedit-access-text-${tid}">${ACCESS_OPTIONS}</select>
        </div>
        <div class="tedit-actions">
          <button class="btn-primary tedit-submit-text" data-id="${tid}" data-domain="${escapeHtml(t.domain)}">Add to Knowledge Base</button>
          <button class="btn-secondary tedit-cancel" data-id="${tid}">Cancel</button>
        </div>
        <div class="tedit-feedback hidden" id="tedit-fb-text-${tid}"></div>
      </div>

      <!-- Upload document mode -->
      <div class="tedit-mode hidden" id="tedit-upload-${tid}">
        <div class="field-group">
          <label>Source type</label>
          <select id="tedit-src-${tid}">
            <option value="pdf">PDF Document</option>
            <option value="confluence_html">Confluence (HTML export)</option>
            <option value="teams">Teams Transcript (.vtt / .json)</option>
          </select>
        </div>
        <div class="field-group">
          <label>File</label>
          <input type="file" id="tedit-file-${tid}" accept=".pdf,.html,.htm,.vtt,.json" />
        </div>
        <div class="field-group">
          <label>Access level</label>
          <select id="tedit-access-upload-${tid}">${ACCESS_OPTIONS}</select>
        </div>
        <div class="tedit-actions">
          <button class="btn-primary tedit-submit-upload" data-id="${tid}" data-domain="${escapeHtml(t.domain)}">Upload &amp; Add to Knowledge Base</button>
          <button class="btn-secondary tedit-cancel" data-id="${tid}">Cancel</button>
        </div>
        <div class="tedit-feedback hidden" id="tedit-fb-upload-${tid}"></div>
      </div>
    </div>` : ""}`;

  // ── Answer Ticket toggle ──────────────────────────────────────
  div.querySelector(".ticket-answer-btn")?.addEventListener("click", function () {
    document.getElementById(`tedit-panel-${this.dataset.id}`).classList.toggle("hidden");
  });

  // ── Tab switching ─────────────────────────────────────────────
  div.querySelectorAll(".tedit-tab").forEach(tab => {
    tab.addEventListener("click", function () {
      const panel = document.getElementById(`tedit-panel-${tid}`);
      panel.querySelectorAll(".tedit-tab").forEach(t => t.classList.remove("tedit-tab-active"));
      this.classList.add("tedit-tab-active");
      panel.querySelectorAll(".tedit-mode").forEach(m => m.classList.add("hidden"));
      document.getElementById(`tedit-${this.dataset.mode}-${tid}`).classList.remove("hidden");
    });
  });

  // ── Cancel ────────────────────────────────────────────────────
  div.querySelectorAll(".tedit-cancel").forEach(btn => {
    btn.addEventListener("click", function () {
      document.getElementById(`tedit-panel-${this.dataset.id}`).classList.add("hidden");
    });
  });

  // ── Submit: write answer ──────────────────────────────────────
  div.querySelector(".tedit-submit-text")?.addEventListener("click", async function () {
    const id     = this.dataset.id;
    const domain = this.dataset.domain;
    const title  = document.getElementById(`tedit-title-${id}`).value.trim();
    const body   = document.getElementById(`tedit-body-${id}`).value.trim();
    const access = document.getElementById(`tedit-access-text-${id}`).value;
    const fb     = document.getElementById(`tedit-fb-text-${id}`);
    if (!body) { showTeditFeedback(fb, "Please enter an answer.", "error"); return; }

    this.disabled    = true;
    this.textContent = "Adding…";
    try {
      const res  = await fetch("/api/ingest/text", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: body, title, domain, access_level: access, ticket_id: id }),
      });
      const data = await res.json();
      if (!res.ok) { showTeditFeedback(fb, data.error || "Failed.", "error"); return; }
      showTeditFeedback(fb, `&#10003; Added ${data.newly_indexed} chunk(s) to the knowledge base.`, "success");
      refreshIndexStatus();
      setTimeout(loadTickets, 1200);
    } catch { showTeditFeedback(fb, "Network error.", "error"); }
    finally  { this.disabled = false; this.textContent = "Add to Knowledge Base"; }
  });

  // ── Submit: upload document ───────────────────────────────────
  div.querySelector(".tedit-submit-upload")?.addEventListener("click", async function () {
    const id       = this.dataset.id;
    const domain   = this.dataset.domain;
    const fileEl   = document.getElementById(`tedit-file-${id}`);
    const srcType  = document.getElementById(`tedit-src-${id}`).value;
    const access   = document.getElementById(`tedit-access-upload-${id}`).value;
    const fb       = document.getElementById(`tedit-fb-upload-${id}`);
    if (!fileEl.files.length) { showTeditFeedback(fb, "Please select a file.", "error"); return; }

    this.disabled    = true;
    this.textContent = "Uploading…";
    const fd = new FormData();
    fd.append("file", fileEl.files[0]);
    fd.append("source_type",  srcType);
    fd.append("access_level", access);
    fd.append("domain",       domain);
    try {
      const res  = await fetch("/api/ingest", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) { showTeditFeedback(fb, data.error || "Failed.", "error"); return; }
      // Mark ticket resolved
      await fetch(`/api/tickets/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "resolved" }),
      });
      showTeditFeedback(fb, `&#10003; Uploaded and added ${data.newly_indexed} chunk(s).`, "success");
      refreshIndexStatus();
      setTimeout(loadTickets, 1200);
    } catch { showTeditFeedback(fb, "Network error.", "error"); }
    finally  { this.disabled = false; this.textContent = "Upload & Add to Knowledge Base"; }
  });

  // ── Mark resolved / Reopen ────────────────────────────────────
  div.querySelector(".ticket-resolve-btn, .ticket-reopen-btn")?.addEventListener("click", async function () {
    const res = await fetch(`/api/tickets/${this.dataset.id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: this.dataset.status }),
    });
    if (res.ok) loadTickets();
    else { const d = await res.json(); alert(d.error || "Update failed."); }
  });

  return div;
}

function showTeditFeedback(el, msg, type) {
  el.innerHTML   = msg;
  el.className   = `tedit-feedback tedit-feedback-${type}`;
  el.classList.remove("hidden");
}


/* ═══════════════════════════════════════════════════════════════
   TAB 6 — INSIGHTS
════════════════════════════════════════════════════════════════ */
let confChartInstance   = null;
let domainChartInstance = null;

document.getElementById("refresh-insights-btn")?.addEventListener("click", loadInsights);
document.getElementById("generate-report-btn")?.addEventListener("click", generateGapReport);

async function loadInsights() {
  const statsEl = document.getElementById("chart-stats");
  statsEl.innerHTML = `<div class="placeholder" style="padding:20px"><p>Loading…</p></div>`;

  try {
    const data = await (await fetch("/api/insights")).json();
    renderConfidenceChart(data.distribution, data.total);
    renderChartStats(data.distribution, data.total);
    if (currentUser?.role === "admin" && Object.keys(data.by_domain || {}).length) {
      renderDomainChart(data.by_domain);
      document.getElementById("domain-breakdown-section").style.display = "";
    }
  } catch {
    statsEl.innerHTML = `<div class="error-box">Failed to load insights.</div>`;
  }
}

function renderConfidenceChart(dist, total) {
  const ctx = document.getElementById("conf-chart").getContext("2d");
  if (confChartInstance) confChartInstance.destroy();
  confChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["HIGH", "MEDIUM", "LOW"],
      datasets: [{
        data:            [dist.HIGH || 0, dist.MEDIUM || 0, dist.LOW || 0],
        backgroundColor: ["#16a34a", "#ca8a04", "#dc2626"],
        borderWidth:     3,
        borderColor:     "#fff",
        hoverOffset:     6,
      }],
    },
    options: {
      cutout: "62%",
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 12 }, padding: 16 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const pct = total ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
              return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

function renderChartStats(dist, total) {
  const statsEl = document.getElementById("chart-stats");
  const pct = v => total ? ((v / total) * 100).toFixed(1) : "0.0";
  statsEl.innerHTML = `
    <div class="chart-stat-item">
      <span class="chart-stat-label">Total queries</span>
      <strong class="chart-stat-value">${total}</strong>
    </div>
    <div class="chart-stat-item">
      <span class="chart-stat-dot" style="background:#16a34a"></span>
      <span class="chart-stat-label">HIGH confidence</span>
      <strong class="chart-stat-value">${dist.HIGH || 0}</strong>
      <span class="chart-stat-pct">${pct(dist.HIGH || 0)}%</span>
    </div>
    <div class="chart-stat-item">
      <span class="chart-stat-dot" style="background:#ca8a04"></span>
      <span class="chart-stat-label">MEDIUM confidence</span>
      <strong class="chart-stat-value">${dist.MEDIUM || 0}</strong>
      <span class="chart-stat-pct">${pct(dist.MEDIUM || 0)}%</span>
    </div>
    <div class="chart-stat-item chart-stat-alert">
      <span class="chart-stat-dot" style="background:#dc2626"></span>
      <span class="chart-stat-label">LOW confidence</span>
      <strong class="chart-stat-value">${dist.LOW || 0}</strong>
      <span class="chart-stat-pct">${pct(dist.LOW || 0)}%</span>
    </div>`;
}

function renderDomainChart(byDomain) {
  const ctx    = document.getElementById("domain-chart").getContext("2d");
  const labels = Object.keys(byDomain).filter(d => d.toLowerCase() !== "unknown");
  if (domainChartInstance) domainChartInstance.destroy();
  domainChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "HIGH",   data: labels.map(d => byDomain[d].HIGH   || 0), backgroundColor: "#16a34a" },
        { label: "MEDIUM", data: labels.map(d => byDomain[d].MEDIUM || 0), backgroundColor: "#ca8a04" },
        { label: "LOW",    data: labels.map(d => byDomain[d].LOW    || 0), backgroundColor: "#dc2626" },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { stacked: true, ticks: { font: { size: 11 } } },
        y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1, font: { size: 11 } } },
      },
      plugins: { legend: { position: "bottom", labels: { font: { size: 12 }, padding: 14 } } },
    },
  });
}

async function generateGapReport() {
  const content    = document.getElementById("gap-report-content");
  const btnLabel   = document.getElementById("report-btn-label");
  const btnSpinner = document.getElementById("report-btn-spinner");
  const btn        = document.getElementById("generate-report-btn");

  btn.disabled       = true;
  btnLabel.innerHTML = "Generating…";
  btnSpinner.classList.remove("hidden");
  content.innerHTML  = `<div class="placeholder"><div class="placeholder-icon">&#8987;</div><p>Analysing knowledge gaps…</p></div>`;

  try {
    const res  = await fetch("/api/insights/report", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      content.innerHTML = `<div class="error-box">${escapeHtml(data.error || "Failed.")}</div>`;
      return;
    }
    content.innerHTML = `
      <div class="gap-report-meta">Based on ${data.based_on} LOW / MEDIUM confidence quer${data.based_on === 1 ? "y" : "ies"}</div>
      <div class="gap-report-body">${renderMarkdown(data.report || "")}</div>`;
  } catch {
    content.innerHTML = `<div class="error-box">Failed to generate report.</div>`;
  } finally {
    btn.disabled       = false;
    btnLabel.innerHTML = "&#9889; Regenerate";
    btnSpinner.classList.add("hidden");
  }
}

/* ═══════════════════════════════════════════════════════════════
   TAB 7 — KNOWLEDGE BASE EXPLORER
════════════════════════════════════════════════════════════════ */
document.getElementById("refresh-kb-btn")?.addEventListener("click", loadKBExplorer);

const KB_DOMAIN_ICONS = {
  "Legal": "&#9878;", "Finance": "&#128176;", "HR": "&#128101;",
  "Technology": "&#128187;", "Operations": "&#9881;", "Marketing": "&#128226;",
  "Customer Service": "&#127911;", "Data Procurement": "&#128202;",
  "Other": "&#128193;", "Unknown": "&#128218;",
};
const KB_SRC_ICONS = { "pdf": "&#128196;", "teams": "&#128172;", "confluence": "&#128279;" };

async function loadKBExplorer() {
  const grid    = document.getElementById("kb-sector-grid");
  const statsBar = document.getElementById("kb-stats-bar");
  grid.innerHTML = `<div class="placeholder"><div class="placeholder-icon">&#8987;</div><p>Loading knowledge base…</p></div>`;
  statsBar.innerHTML = "";

  try {
    const res  = await fetch("/api/kb/documents");
    const docs = await res.json();
    if (res.status === 403) {
      grid.innerHTML = `<div class="error-box">Access restricted.</div>`;
      return;
    }
    if (!docs.length) {
      grid.innerHTML = `<div class="placeholder"><div class="placeholder-icon">&#128218;</div><p>No documents in the knowledge base yet. Ingest some documents first.</p></div>`;
      return;
    }

    // Group by domain
    const sectors = {};
    let totalChunks = 0;
    for (const doc of docs) {
      const d = doc.domain || "Unknown";
      if (!sectors[d]) sectors[d] = [];
      sectors[d].push(doc);
      totalChunks += doc.chunk_count;
    }
    const domainCount = Object.keys(sectors).length;

    // Render stats bar
    statsBar.innerHTML = `
      <div class="kb-stat-card animate-in stagger-1">
        <div class="kb-stat-value">${docs.length}</div>
        <div class="kb-stat-label">Documents</div>
      </div>
      <div class="kb-stat-card animate-in stagger-2">
        <div class="kb-stat-value">${domainCount}</div>
        <div class="kb-stat-label">Domains</div>
      </div>
      <div class="kb-stat-card animate-in stagger-3">
        <div class="kb-stat-value">${totalChunks.toLocaleString()}</div>
        <div class="kb-stat-label">Indexed Segments</div>
      </div>`;

    // Render sector cards
    grid.innerHTML = "";
    Object.entries(sectors).sort(([a], [b]) => a.localeCompare(b))
      .forEach(([domain, domDocs], idx) => {
        const card = document.createElement("div");
        card.className = `kb-sector-card stagger-${Math.min(idx + 1, 10)}`;
        const icon = KB_DOMAIN_ICONS[domain] || "&#128193;";
        card.innerHTML = `
          <div class="kb-sector-header">
            <div class="kb-sector-icon">${icon}</div>
            <span class="kb-sector-name">${escapeHtml(domain)}</span>
            <span class="kb-sector-count">${domDocs.length} doc${domDocs.length !== 1 ? "s" : ""}</span>
          </div>
          <div class="kb-doc-list">
            ${domDocs.map(doc => {
              const srcIcon = KB_SRC_ICONS[doc.source_system] || "&#128196;";
              const author  = doc.author !== "—" ? `&#128100; ${escapeHtml(doc.author)}` : "";
              const date    = doc.date   !== "—" ? `&#128197; ${escapeHtml(doc.date)}`   : "";
              return `
                <div class="kb-doc-item">
                  <div class="kb-doc-icon">${srcIcon}</div>
                  <div class="kb-doc-info">
                    <div class="kb-doc-title" title="${escapeHtml(doc.source_file)}">${escapeHtml(doc.title || doc.source_file)}</div>
                    <div class="kb-doc-meta">
                      <span class="badge badge-${doc.access_level}">${escapeHtml(doc.access_level)}</span>
                      ${author ? `<span>${author}</span>` : ""}
                      ${date   ? `<span>${date}</span>`   : ""}
                    </div>
                  </div>
                </div>`;
            }).join("")}
          </div>`;
        grid.appendChild(card);
      });
  } catch {
    grid.innerHTML = `<div class="error-box">Failed to load knowledge base.</div>`;
  }
}


function renderMarkdown(text) {
  /* Lightweight markdown → HTML converter for the gap report.
     Handles: # headings, **bold**, *italic*, bullet lists (•/-/*), numbered
     lists, and paragraphs.  escapeHtml is applied before inline substitutions
     so user-supplied content can never inject raw HTML. */
  function inline(str) {
    return escapeHtml(str)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g,     "<em>$1</em>");
  }

  const lines = text.split("\n");
  let html = "", inList = false, listTag = "ul";

  const closeList = () => { if (inList) { html += `</${listTag}>`; inList = false; } };

  for (const raw of lines) {
    const line = raw.trim();

    if (!line) { closeList(); continue; }

    // ATX headings: #, ##, ###
    const hMatch = line.match(/^(#{1,3})\s+(.*)/);
    if (hMatch) {
      closeList();
      const level = Math.min(hMatch[1].length + 2, 5); // h3–h5
      html += `<h${level} class="gap-report-heading">${inline(hMatch[2])}</h${level}>`;
      continue;
    }

    // Setext-style bold section titles (e.g. "UNCOVERED TOPICS:")
    if (line === line.toUpperCase() && line.length < 60 && /[A-Z]{3}/.test(line)) {
      closeList();
      html += `<p class="gap-report-section-title">${inline(line)}</p>`;
      continue;
    }

    // Bullet list: •, -, *
    const bulletMatch = line.match(/^[•\-\*]\s+(.*)/);
    if (bulletMatch) {
      if (!inList) { html += `<ul class="gap-report-list">`; inList = true; listTag = "ul"; }
      html += `<li class="gap-report-item">${inline(bulletMatch[1])}</li>`;
      continue;
    }

    // Numbered list: 1. 2. etc.
    const numMatch = line.match(/^\d+\.\s+(.*)/);
    if (numMatch) {
      if (!inList) { html += `<ol class="gap-report-list">`; inList = true; listTag = "ol"; }
      html += `<li class="gap-report-item">${inline(numMatch[1])}</li>`;
      continue;
    }

    closeList();
    html += `<p class="gap-report-para">${inline(line)}</p>`;
  }

  closeList();
  return html;
}
