"""
Persistent store for user training progress.

Records each attempt and exposes aggregate statistics
(total points, streaks, level) for the gamified training UI.
"""

import json
import logging
import os
from datetime import date, datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

USER_PROGRESS_PATH = "data/user_progress.jsonl"

_LEVEL_THRESHOLDS = [
    (150, "Expert"),
    (80,  "Specialist"),
    (30,  "Analyst"),
    (0,   "Trainee"),
]


def _level_for_points(points: int) -> str:
    for threshold, name in _LEVEL_THRESHOLDS:
        if points >= threshold:
            return name
    return "Trainee"


class UserProgressStore:
    """Append-only JSONL store for per-user training attempt records."""

    def record(
        self,
        user_id: str,
        question_id: str,
        domain: str,
        score: int,
        feedback: str,
        strengths: list,
        improvements: list,
    ) -> dict:
        now = datetime.now(timezone.utc)
        entry = {
            "user_id":      user_id,
            "question_id":  question_id,
            "domain":       domain,
            "score":        score,
            "feedback":     feedback,
            "strengths":    strengths,
            "improvements": improvements,
            "date":         now.strftime("%Y-%m-%d"),
            "timestamp":    now.isoformat(),
        }
        os.makedirs("data", exist_ok=True)
        try:
            with open(USER_PROGRESS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("User progress write failed: %s", exc)
        return entry

    def _load_all(self) -> List[dict]:
        if not os.path.exists(USER_PROGRESS_PATH):
            return []
        entries = []
        with open(USER_PROGRESS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping malformed progress line: %s", exc)
        return entries

    def get_user_history(self, user_id: str) -> List[dict]:
        """Returns all attempts for a user, newest first."""
        entries = [e for e in self._load_all() if e.get("user_id") == user_id]
        return sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)

    def get_user_stats(self, user_id: str) -> dict:
        """Returns aggregate statistics for the user."""
        history = self.get_user_history(user_id)

        total_attempts = len(history)
        total_points   = sum(max(1, e.get("score", 0) // 10) for e in history)
        average_score  = (
            round(sum(e.get("score", 0) for e in history) / total_attempts)
            if total_attempts else 0
        )

        # Streak: consecutive days with at least one attempt, ending today or yesterday
        attempt_dates = sorted(
            {e["date"] for e in history if e.get("date")},
            reverse=True,
        )
        streak = 0
        if attempt_dates:
            today     = date.today()
            yesterday = date.fromordinal(today.toordinal() - 1)
            # Streak must include today or yesterday to be active
            first = date.fromisoformat(attempt_dates[0])
            if first in (today, yesterday):
                streak = 1
                prev = first
                for ds in attempt_dates[1:]:
                    d = date.fromisoformat(ds)
                    if (prev.toordinal() - d.toordinal()) == 1:
                        streak += 1
                        prev = d
                    else:
                        break

        level = _level_for_points(total_points)
        domains_practiced = list(
            {e.get("domain", "") for e in history if e.get("domain")}
        )

        return {
            "total_attempts":    total_attempts,
            "total_points":      total_points,
            "average_score":     average_score,
            "streak":            streak,
            "level":             level,
            "domains_practiced": domains_practiced,
        }
