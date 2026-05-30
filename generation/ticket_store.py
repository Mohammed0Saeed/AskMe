"""
Persistent store for knowledge-gap tickets.

A ticket is created automatically whenever a query produces a LOW-confidence
answer, signalling that the knowledge base does not cover that topic well enough.
Experts see tickets scoped to their domain; admins see all tickets.

JSONL-backed for the same reasons as the audit log: human-readable, grep-able,
no schema migrations, and trivially importable into pandas for analysis.
"""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

TICKETS_PATH = "data/tickets.jsonl"


@dataclass
class Ticket:
    ticket_id:          str
    created_at:         str
    query:              str
    answer:             str
    confidence_level:   str   # "LOW" (only LOW creates tickets)
    confidence_reason:  str
    domain:             str   # inferred from citations / retrieval / domain_filter
    no_data:            bool  # True when LLM said "I don't know…"
    user_id:            str
    user_name:          str
    audit_id:           str
    status:             str   # "open" | "resolved"


class TicketStore:
    """
    Append-only JSONL ticket store with a rewrite-on-update pattern.
    The file is small enough (tickets are rare — only on LOW confidence) that
    a full rewrite on status change is acceptable and avoids a database dependency.
    """

    def create(
        self,
        query:             str,
        answer:            str,
        confidence_level:  str,
        confidence_reason: str,
        domain:            str,
        no_data:           bool,
        user_id:           str,
        user_name:         str,
        audit_id:          str,
    ) -> Ticket:
        ticket = Ticket(
            ticket_id         = f"tkt_{uuid.uuid4().hex[:8]}",
            created_at        = datetime.now(timezone.utc).isoformat(),
            query             = query,
            answer            = answer,
            confidence_level  = confidence_level,
            confidence_reason = confidence_reason,
            domain            = domain,
            no_data           = no_data,
            user_id           = user_id,
            user_name         = user_name,
            audit_id          = audit_id,
            status            = "open",
        )
        os.makedirs("data", exist_ok=True)
        try:
            with open(TICKETS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(ticket), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Ticket write failed: %s", exc)
        return ticket

    def _load_all(self) -> List[Ticket]:
        """Reads every ticket from disk in chronological order."""
        if not os.path.exists(TICKETS_PATH):
            return []
        tickets = []
        with open(TICKETS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    tickets.append(Ticket(**json.loads(line)))
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("Skipping malformed ticket line: %s", exc)
        return tickets

    def get_all(self, domain: Optional[str] = None) -> List[Ticket]:
        """Returns tickets newest-first, optionally filtered by domain."""
        tickets = sorted(self._load_all(), key=lambda t: t.created_at, reverse=True)
        if domain:
            tickets = [t for t in tickets if t.domain == domain]
        return tickets

    def update_status(self, ticket_id: str, status: str) -> Optional[Ticket]:
        """Updates a ticket's status and rewrites the file."""
        tickets = self._load_all()
        updated = None
        for t in tickets:
            if t.ticket_id == ticket_id:
                t.status = status
                updated = t
                break
        if updated is None:
            return None
        os.makedirs("data", exist_ok=True)
        with open(TICKETS_PATH, "w", encoding="utf-8") as f:
            for t in tickets:
                f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")
        return updated
