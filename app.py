import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session

from collections import Counter

from auth import UserStore
from config import GEMINI_MODEL, LLM_PROVIDER, OLLAMA_MODEL, RELEVANCE_THRESHOLD, SECRET_KEY
from generation import GenerationPipeline
from generation.audit_logger import read_by_id, read_recent
from generation.insight_engine import InsightEngine
from generation.ticket_store import TicketStore
from ingestion import IngestionPipeline
from retrieval import RetrievalPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.secret_key = SECRET_KEY

# ── Singletons ───────────────────────────────────────────────────────────────
user_store          = UserStore()
ingest_pipeline     = IngestionPipeline()
retrieval_pipeline  = RetrievalPipeline()
generation_pipeline = GenerationPipeline()
ticket_store        = TicketStore()
insight_engine      = InsightEngine()
retrieval_pipeline.load_index()

ALLOWED_EXTENSIONS = {".pdf", ".vtt", ".json", ".html", ".htm"}

# ── Conversational query detection ─────────────────────────────────────────────
_CONV_STARTERS = {"hi", "hello", "hey", "howdy", "hiya", "yo", "greetings", "sup"}
_CONV_PHRASES  = {
    "how are you", "how r u", "how are u", "hows it going", "how's it going",
    "whats up", "what's up", "what is up",
    "good morning", "good afternoon", "good evening", "good night",
    "nice to meet you", "pleased to meet you", "great to meet you",
    "who are you", "what are you", "what can you do", "what do you do",
    "thanks", "thank you", "thank u", "cheers", "many thanks", "appreciated",
    "bye", "goodbye", "ciao", "see you", "see ya", "farewell", "take care",
    "ok", "okay", "got it", "sounds good", "great", "awesome", "cool",
}

def _is_conversational(query: str) -> bool:
    q     = query.strip().lower().rstrip("!?.")
    words = q.split()
    if not words:
        return False
    if q in _CONV_STARTERS or q in _CONV_PHRASES:
        return True
    # Short message starting with a known greeting word (≤ 5 words)
    return words[0] in _CONV_STARTERS and len(words) <= 5
INGEST_LOG_PATH    = "data/ingest_log.jsonl"

# Roles that are allowed to ingest documents
INGEST_ROLES = {"expert", "admin"}

# Access levels that trigger the confidential notice for regular users
RESTRICTED_LEVELS = {"confidential", "restricted"}


# ── Auth helpers ──────────────────────────────────────────────────────────────

def get_current_user():
    """Returns the logged-in User object, or None if the session is empty."""
    uid = session.get("user_id")
    return user_store.find_by_id(uid) if uid else None


def login_required(f):
    """
    Decorator that enforces authentication on every route it wraps.
    API routes get a 401 JSON response so the frontend can redirect to /login
    without the browser following a server-side redirect inside a fetch() call.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Restricts a route to admin users only."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required."}), 403
        return f(*args, **kwargs)
    return decorated


# ── Serialisers ───────────────────────────────────────────────────────────────

def _chunk_to_dict(chunk) -> dict:
    """Converts a DocumentChunk to a JSON-safe dict, stripping internal temp paths."""
    return {
        "chunk_id": chunk.chunk_id[:8],
        "content":  chunk.content,
        "metadata": {
            "author":        chunk.metadata.author,
            "date":          chunk.metadata.date,
            "source_system": chunk.metadata.source_system,
            "access_level":  chunk.metadata.access_level,
            "domain":        chunk.metadata.domain,
            "source_file":   os.path.basename(chunk.metadata.source_file),
            "chunk_index":   chunk.metadata.chunk_index,
            "title":         chunk.metadata.title or "",
            "page_number":   chunk.metadata.page_number,
            "url":           chunk.metadata.url or "",
        },
    }


def _result_to_dict(result) -> dict:
    return {
        "rank":         result.rank,
        "rerank_score": round(result.rerank_score, 4),
        "vector_score": round(result.vector_score, 4),
        "bm25_score":   round(result.bm25_score,   4),
        "rrf_score":    round(result.rrf_score,     6),
        "chunk":        _chunk_to_dict(result.chunk),
    }


def _citation_to_dict(c) -> dict:
    return {
        "ref_id":         c.ref_id,
        "chunk_id":       c.chunk_id,
        "source_file":    c.source_file,
        "author":         c.author,
        "domain":         c.domain,
        "access_level":   c.access_level,
        "page_number":    c.page_number,
        "relevant_quote": c.relevant_quote,
    }


def _build_confidential_notice(results, user) -> dict | None:
    """
    Checks whether any retrieved chunk is confidential or restricted and,
    if the requesting user is a regular user, returns a notice object with
    expert contact information so they know who to approach for validation.
    Experts and admins see confidential content without a notice.
    """
    if user.role != "user":
        return None

    restricted_domains = {
        r.chunk.metadata.domain
        for r in results
        if r.chunk.metadata.access_level in RESTRICTED_LEVELS
    }
    if not restricted_domains:
        return None

    contacts = []
    for domain in restricted_domains:
        expert = user_store.find_expert_for_domain(domain)
        if expert:
            contacts.append({
                "domain": domain,
                "name":   expert.name,
                "email":  expert.email,
            })

    return {
        "has_restricted": True,
        "domains":        list(restricted_domains),
        "contacts":       contacts,
    }


def _infer_domain(gen, results, domain_filter: str | None) -> str:
    """
    Determines the most likely domain for a ticket.
    Priority: explicit domain_filter > most common citation domain > top chunk domain.
    """
    if domain_filter:
        return domain_filter
    if gen.citations:
        domains = [c.domain for c in gen.citations if c.domain]
        if domains:
            return Counter(domains).most_common(1)[0][0]
    if results:
        return results[0].chunk.metadata.domain or "Unknown"
    return "Unknown"


def _write_ingest_log(user, filename: str, chunks: int, domain: str) -> None:
    """
    Appends one line to the ingest activity log so admins can see who uploaded
    what and when — mirroring the query audit trail for document ingestion.
    """
    os.makedirs("data", exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id":   user.user_id,
        "user_name": user.name,
        "role":      user.role,
        "filename":  filename,
        "chunks":    chunks,
        "domain":    domain,
    }
    with open(INGEST_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/login")
def login_page():
    """Serves the login page; redirects to the app if already authenticated."""
    if session.get("user_id"):
        return redirect("/")
    return render_template("login.html")


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """
    Validates credentials and starts a session.
    Returns the user's public profile so the frontend can populate
    the header and enforce role-based UI rules immediately on login.
    """
    body     = request.get_json(force=True) or {}
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    user = user_store.find_by_email(email)
    if not user or not user_store.verify_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"] = user.user_id
    session.permanent = True
    return jsonify(user.to_public_dict())


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Returns the current user's profile. 401 if not logged in."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
    return jsonify(user.to_public_dict())


# ── Main page ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html")


# ── Ingest ────────────────────────────────────────────────────────────────────

@app.route("/api/ingest", methods=["POST"])
@login_required
def ingest():
    """
    Ingests a document into the knowledge base.
    Access rules:
      - Regular users cannot ingest (return 403).
      - Experts can only ingest documents for their own domain; uploading a
        document tagged to a different domain is blocked with a clear message.
      - Admins can ingest for any domain.
    """
    user = get_current_user()

    if user.role not in INGEST_ROLES:
        return jsonify({
            "error": "Uploading documents is restricted to experts and admins. "
                     "Please contact the relevant expert to add content.",
            "role_restricted": True,
        }), 403

    source_type  = request.form.get("source_type", "pdf")
    access_level = request.form.get("access_level", "internal")
    domain       = request.form.get("domain", "").strip()

    # Expert domain enforcement
    if user.role == "expert":
        if not domain:
            domain = user.domain  # auto-assign expert's domain when left blank
        elif domain != user.domain:
            return jsonify({
                "error": (
                    f"You are authorised to upload documents for the "
                    f"'{user.domain}' domain only. "
                    f"This document is labelled '{domain}'. "
                    f"Please contact the {domain} expert to handle this upload."
                ),
                "domain_mismatch": True,
                "your_domain":     user.domain,
                "attempted_domain": domain,
            }), 403

    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files["file"]
    ext  = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type '{ext}' is not supported."}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        file.save(tmp_path)

    try:
        if source_type == "pdf":
            chunks = ingest_pipeline.ingest_pdf(tmp_path, access_level=access_level, domain=domain)
        elif source_type == "confluence_html":
            chunks = ingest_pipeline.ingest_confluence_html(tmp_path, access_level=access_level, domain=domain)
        elif source_type == "teams":
            chunks = ingest_pipeline.ingest_teams_transcript(
                tmp_path,
                meeting_organiser=request.form.get("meeting_organiser", ""),
                meeting_date=request.form.get("meeting_date", ""),
                meeting_title=request.form.get("meeting_title", ""),
                access_level=access_level,
                domain=domain,
            )
        else:
            return jsonify({"error": f"Unknown source type: {source_type}"}), 400

        added = retrieval_pipeline.index(chunks)
        _write_ingest_log(user, file.filename, added, domain)

        return jsonify({
            "success":       True,
            "total_chunks":  len(chunks),
            "newly_indexed": added,
            "index_size":    retrieval_pipeline.total_chunks,
            "chunks":        [_chunk_to_dict(c) for c in chunks],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        os.unlink(tmp_path)


# ── Ask ───────────────────────────────────────────────────────────────────────

@app.route("/api/ask", methods=["POST"])
@login_required
def ask():
    """
    Full RAG pipeline with role-aware post-processing:
      - Regular users receive a confidential_notice when any retrieved chunk
        is tagged confidential/restricted, directing them to the expert.
      - Experts and admins see no notice.
    """
    user         = get_current_user()
    body         = request.get_json(force=True) or {}
    query        = (body.get("query") or "").strip()
    top_k        = int(body.get("top_k", 5))
    access_level = body.get("access_level") or None
    domain       = (body.get("domain_filter") or "").strip() or None

    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    if _is_conversational(query):
        try:
            gen = generation_pipeline.generate_conversational(query)
            tu  = gen.token_usage
            return jsonify({
                "query":    query,
                "no_data":  False,
                "answer":   gen.answer,
                "citations": [],
                "confidence": {"level": "HIGH", "score": 1.0, "reason": "Conversational response."},
                "token_usage": {
                    "prompt_tokens":     tu.prompt_tokens     if tu else 0,
                    "completion_tokens": tu.completion_tokens if tu else 0,
                    "total_tokens":      tu.total_tokens      if tu else 0,
                    "estimated":         tu.estimated         if tu else True,
                },
                "confidential_notice": None,
                "audit_id": None,
                "model":    gen.model,
                "results":  [],
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    if retrieval_pipeline.total_chunks == 0:
        return jsonify({"error": "Index is empty. Please contact an admin or expert."}), 400

    provider_label = f"ollama / {OLLAMA_MODEL}" if LLM_PROVIDER == "ollama" else "Gemini"

    try:
        results = retrieval_pipeline.search(query, top_k=top_k,
                                            user_access_level=access_level,
                                            domain_filter=domain)
        if not results:
            return jsonify({"error": "No relevant documents found."}), 404

        if results[0].rerank_score < RELEVANCE_THRESHOLD:
            return jsonify({
                "query": query, "no_data": True,
                "answer": "I don't know, please ask your supervisor.",
                "citations": [],
                "confidence": {"level": "LOW", "score": 0.0,
                               "reason": "Retrieved documents are not relevant to this question."},
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0,
                                "total_tokens": 0, "estimated": True},
                "confidential_notice": None,
                "audit_id": None, "model": provider_label,
                "results": [_result_to_dict(r) for r in results],
            })

        gen = generation_pipeline.generate(query, results)
        tu  = gen.token_usage

        # Auto-create a ticket when confidence is LOW so experts can review gaps
        if gen.confidence.level == "LOW":
            ticket_store.create(
                query             = query,
                answer            = gen.answer,
                confidence_level  = gen.confidence.level,
                confidence_reason = gen.confidence.reason,
                domain            = _infer_domain(gen, results, domain),
                no_data           = gen.no_data,
                user_id           = user.user_id,
                user_name         = user.name,
                audit_id          = gen.audit_id,
            )

        return jsonify({
            "query":     query,
            "no_data":   gen.no_data,
            "answer":    gen.answer,
            "citations": [_citation_to_dict(c) for c in gen.citations],
            "confidence": {
                "level":  gen.confidence.level,
                "score":  gen.confidence.score,
                "reason": gen.confidence.reason,
            },
            "token_usage": {
                "prompt_tokens":     tu.prompt_tokens     if tu else 0,
                "completion_tokens": tu.completion_tokens if tu else 0,
                "total_tokens":      tu.total_tokens      if tu else 0,
                "estimated":         tu.estimated         if tu else True,
            },
            "confidential_notice": _build_confidential_notice(results, user),
            "audit_id":  gen.audit_id,
            "model":     gen.model,
            "results":   [_result_to_dict(r) for r in results],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Experts directory (public) ────────────────────────────────────────────────

@app.route("/api/experts", methods=["GET"])
@login_required
def get_experts():
    """Returns the list of experts so the frontend can build confidential notices."""
    return jsonify([e.to_public_dict() for e in user_store.get_experts()])


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    """Returns all users for the admin management panel."""
    return jsonify([u.to_public_dict() for u in user_store.get_all()])


@app.route("/api/admin/users/<user_id>", methods=["PUT"])
@admin_required
def admin_update_user(user_id: str):
    """
    Admin-only: updates a user's role and domain.
    Clearing domain automatically when role is not 'expert' prevents stale
    domain data from bypassing access-control checks.
    """
    body   = request.get_json(force=True) or {}
    role   = body.get("role", "user")
    domain = body.get("domain", "")
    updated = user_store.update_user(user_id, role, domain)
    if not updated:
        return jsonify({"error": "User not found."}), 404
    return jsonify(updated.to_public_dict())


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    """Admin-only: creates a new user with the firstname_1234 password convention."""
    body   = request.get_json(force=True) or {}
    name   = (body.get("name") or "").strip()
    email  = (body.get("email") or "").strip()
    role   = body.get("role", "user")
    domain = body.get("domain", "")
    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400
    user = user_store.create_user(name, email, role, domain)
    return jsonify(user.to_public_dict()), 201


@app.route("/api/admin/activity", methods=["GET"])
@admin_required
def admin_activity():
    """
    Returns a merged activity summary: queries from audit_log.jsonl and
    ingestions from data/ingest_log.jsonl, grouped by user so the admin
    can see at a glance who is doing what.
    """
    users   = {u.user_id: u.to_public_dict() for u in user_store.get_all()}
    queries = _read_jsonl("audit_log.jsonl")
    ingests = _read_jsonl(INGEST_LOG_PATH)

    summary = {uid: {**udata, "queries": 0, "ingests": 0, "last_activity": ""}
               for uid, udata in users.items()}

    for entry in queries:
        uid = entry.get("user_id")
        if uid and uid in summary:
            summary[uid]["queries"] += 1
            ts = entry.get("timestamp", "")
            if ts > summary[uid]["last_activity"]:
                summary[uid]["last_activity"] = ts

    for entry in ingests:
        uid = entry.get("user_id")
        if uid and uid in summary:
            summary[uid]["ingests"] += 1
            ts = entry.get("timestamp", "")
            if ts > summary[uid]["last_activity"]:
                summary[uid]["last_activity"] = ts

    return jsonify(list(summary.values()))


def _read_jsonl(path: str) -> list:
    """Reads a JSONL file safely, skipping malformed lines."""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    return entries


# ── Misc ──────────────────────────────────────────────────────────────────────

@app.route("/api/search", methods=["POST"])
@login_required
def search():
    body         = request.get_json(force=True) or {}
    query        = (body.get("query") or "").strip()
    top_k        = int(body.get("top_k", 5))
    access_level = body.get("access_level") or None
    domain       = (body.get("domain_filter") or "").strip() or None
    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400
    if retrieval_pipeline.total_chunks == 0:
        return jsonify({"error": "Index is empty."}), 400
    try:
        results = retrieval_pipeline.search(query, top_k=top_k,
                                            user_access_level=access_level,
                                            domain_filter=domain)
        return jsonify({"query": query, "total_results": len(results),
                        "index_size": retrieval_pipeline.total_chunks,
                        "results": [_result_to_dict(r) for r in results]})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/audit", methods=["GET"])
@login_required
def audit_list():
    n = int(request.args.get("n", 20))
    return jsonify({"entries": read_recent(n)})



@app.route("/api/audit/<audit_id>", methods=["GET"])
@login_required
def audit_entry(audit_id: str):
    entry = read_by_id(audit_id)
    if not entry:
        return jsonify({"error": f"Audit entry '{audit_id}' not found."}), 404
    return jsonify(entry)


@app.route("/api/index/stats", methods=["GET"])
@login_required
def index_stats():
    return jsonify({"total_chunks": retrieval_pipeline.total_chunks})


@app.route("/api/admin/kb/clear", methods=["POST"])
@admin_required
def admin_clear_kb():
    """Admin-only: wipes all indexed documents from memory and disk."""
    retrieval_pipeline.clear_index()
    ingest_log = INGEST_LOG_PATH
    if os.path.exists(ingest_log):
        os.remove(ingest_log)
    return jsonify({"success": True, "message": "Knowledge base cleared."})


@app.route("/api/kb/documents", methods=["GET"])
@login_required
def kb_documents():
    """Returns one entry per unique source document for the KB Explorer view."""
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403
    return jsonify(retrieval_pipeline.list_documents())


@app.route("/api/config", methods=["GET"])
@login_required
def get_config():
    if LLM_PROVIDER == "ollama":
        return jsonify({"provider": "ollama", "model": OLLAMA_MODEL,
                        "label": f"Local · {OLLAMA_MODEL}"})
    return jsonify({"provider": "gemini", "model": GEMINI_MODEL,
                    "label": f"Gemini · {GEMINI_MODEL}"})


# ── Ingest from raw text ─────────────────────────────────────────────────────

@app.route("/api/ingest/text", methods=["POST"])
@login_required
def ingest_text():
    """
    Ingests a plain-text answer directly into the knowledge base without a file.
    Used by experts and admins when resolving a ticket by typing the answer.
    Optionally marks a ticket as resolved when ticket_id is supplied.
    Domain enforcement mirrors the file-ingest route: experts are locked to
    their own domain, admins can specify any domain.
    """
    user = get_current_user()
    if user.role not in INGEST_ROLES:
        return jsonify({"error": "Uploading content is restricted to experts and admins."}), 403

    body         = request.get_json(force=True) or {}
    text         = (body.get("text") or "").strip()
    title        = (body.get("title") or "Manual Entry").strip()
    access_level = (body.get("access_level") or "internal").strip()
    domain       = (body.get("domain") or "").strip()
    ticket_id    = (body.get("ticket_id") or "").strip()

    if not text:
        return jsonify({"error": "Text content cannot be empty."}), 400

    if user.role == "expert":
        if not domain:
            domain = user.domain
        elif domain != user.domain:
            return jsonify({"error": f"You are authorised to upload for '{user.domain}' only."}), 403

    try:
        chunks = ingest_pipeline.ingest_text(text, title=title,
                                             access_level=access_level, domain=domain)
        added  = retrieval_pipeline.index(chunks)
        _write_ingest_log(user, title, added, domain)

        if ticket_id:
            ticket_store.update_status(ticket_id, "resolved")

        return jsonify({
            "success":       True,
            "total_chunks":  len(chunks),
            "newly_indexed": added,
            "index_size":    retrieval_pipeline.total_chunks,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Tickets ───────────────────────────────────────────────────────────────────

@app.route("/api/tickets", methods=["GET"])
@login_required
def get_tickets():
    """
    Returns knowledge-gap tickets scoped by role:
      - expert : only tickets whose domain matches the expert's own domain
      - admin  : all tickets; accepts optional ?domain= query param to filter
    Regular users cannot access tickets (403).
    """
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403

    if user.role == "expert":
        tickets = ticket_store.get_all(domain=user.domain)
    else:
        domain_filter = request.args.get("domain", "").strip() or None
        tickets = ticket_store.get_all(domain=domain_filter)

    return jsonify([vars(t) for t in tickets])


@app.route("/api/tickets/<ticket_id>", methods=["PUT"])
@login_required
def update_ticket(ticket_id: str):
    """Experts and admins can flip a ticket's status between open and resolved."""
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403

    body   = request.get_json(force=True) or {}
    status = body.get("status", "").strip()
    if status not in ("open", "resolved"):
        return jsonify({"error": "status must be 'open' or 'resolved'."}), 400

    ticket = ticket_store.update_status(ticket_id, status)
    if not ticket:
        return jsonify({"error": f"Ticket '{ticket_id}' not found."}), 404
    return jsonify(vars(ticket))


# ── Insights ──────────────────────────────────────────────────────────────────

@app.route("/api/insights", methods=["GET"])
@login_required
def get_insights():
    """
    Returns confidence distribution and per-domain breakdown computed from the
    audit log.  No LLM call — safe to call on every tab load.
    Visible to experts and admins only.
    """
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403
    return jsonify(insight_engine.confidence_distribution())


@app.route("/api/insights/report", methods=["POST"])
@login_required
def get_gap_report():
    """
    Triggers the LLM gap-report generation.  Separated from /api/insights so
    the LLM is only called when the user explicitly requests it, not on every
    page load.  Visible to experts and admins only.
    """
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403
    return jsonify(insight_engine.generate_gap_report())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
