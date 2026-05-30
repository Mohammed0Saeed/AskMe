"""
Persistent store for scenario-based training questions.

Experts create questions for their domain; all users can practice
answering them. Questions are stored in a JSONL file.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

TRAINING_QUESTIONS_PATH = "data/training_questions.jsonl"


class TrainingStore:
    """Append-only JSONL store for training questions with rewrite-on-delete."""

    def create(
        self,
        domain: str,
        situation: str,
        expected_answer: str,
        created_by: str,
        created_by_name: str,
        difficulty: str = "medium",
    ) -> dict:
        question = {
            "question_id":    uuid.uuid4().hex[:12],
            "domain":         domain,
            "situation":      situation,
            "expected_answer": expected_answer,
            "created_by":     created_by,
            "created_by_name": created_by_name,
            "difficulty":     difficulty,
            "created_at":     datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs("data", exist_ok=True)
        try:
            with open(TRAINING_QUESTIONS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(question, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Training question write failed: %s", exc)
        return question

    def _load_all(self) -> List[dict]:
        if not os.path.exists(TRAINING_QUESTIONS_PATH):
            return []
        questions = []
        with open(TRAINING_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    questions.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping malformed training question line: %s", exc)
        return questions

    def get_all(self, domain: Optional[str] = None) -> List[dict]:
        """Returns all questions, optionally filtered by domain, newest first."""
        questions = sorted(
            self._load_all(),
            key=lambda q: q.get("created_at", ""),
            reverse=True,
        )
        if domain:
            questions = [q for q in questions if q.get("domain") == domain]
        return questions

    def delete(self, question_id: str) -> bool:
        """Deletes a question by ID; rewrites the file. Returns True if found."""
        questions = self._load_all()
        original_len = len(questions)
        questions = [q for q in questions if q.get("question_id") != question_id]
        if len(questions) == original_len:
            return False
        os.makedirs("data", exist_ok=True)
        with open(TRAINING_QUESTIONS_PATH, "w", encoding="utf-8") as f:
            for q in questions:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        return True

    def find_by_id(self, question_id: str) -> Optional[dict]:
        """Returns the question dict for the given ID, or None."""
        for q in self._load_all():
            if q.get("question_id") == question_id:
                return q
        return None
