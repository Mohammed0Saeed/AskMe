import hashlib
import json
import os
import uuid
from typing import List, Optional

from auth.models import User

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")


def _hash(password: str) -> str:
    """SHA-256 hash used for demo credentials. Not suitable for production."""
    return hashlib.sha256(password.encode()).hexdigest()


# Pre-seeded users delivered as part of the task specification.
# Passwords follow the firstname_1234 convention.
_SEED_USERS = [
    User("usr_001", "Mohammed Saeed", "mohammed_saeed@six.ch", "admin",    "",          _hash("mohammed_1234")),
    User("usr_002", "Jacob SIX",      "jacob_six@six.ch",      "expert",   "Legal",     _hash("jacob_1234")),
    User("usr_003", "Mirco SIX",      "mirco_six@six.ch",      "expert",   "Marketing", _hash("mirco_1234")),
    User("usr_004", "Steve John",     "steve_john@six.ch",     "user",     "",          _hash("steve_1234")),
]


class UserStore:
    """
    JSON-file-backed user store.  Loads once on construction and writes back
    on every mutation.  The file is created with the seed users if it does not
    exist so the app works out-of-the-box without a database setup step.
    """

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        if not os.path.exists(DATA_PATH):
            self._users: List[User] = list(_SEED_USERS)
            self._save()
        else:
            self._users = self._load()

    def _load(self) -> List[User]:
        """Reads users.json and deserialises every row into a User dataclass."""
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return [User(**row) for row in rows]

    def _save(self) -> None:
        """Persists the in-memory user list to disk."""
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(
                [vars(u) for u in self._users],
                f, indent=2, ensure_ascii=False,
            )

    # ── Lookups ──────────────────────────────────────────────────────────────

    def find_by_email(self, email: str) -> Optional[User]:
        """Case-insensitive email lookup used by the login endpoint."""
        email = email.strip().lower()
        return next((u for u in self._users if u.email.lower() == email), None)

    def find_by_id(self, user_id: str) -> Optional[User]:
        return next((u for u in self._users if u.user_id == user_id), None)

    def get_all(self) -> List[User]:
        return list(self._users)

    def get_experts(self) -> List[User]:
        """Returns experts with their domain — used to build the confidential-notice contacts."""
        return [u for u in self._users if u.role == "expert"]

    def find_expert_for_domain(self, domain: str) -> Optional[User]:
        """Returns the expert responsible for a given domain, or None."""
        return next((u for u in self._users if u.role == "expert" and u.domain == domain), None)

    # ── Auth ─────────────────────────────────────────────────────────────────

    def verify_password(self, plain: str, stored_hash: str) -> bool:
        """Compares a plaintext password against its stored SHA-256 hash."""
        return _hash(plain) == stored_hash

    # ── Admin mutations ───────────────────────────────────────────────────────

    def update_user(self, user_id: str, role: str, domain: str) -> Optional[User]:
        """
        Updates role and domain for a user.  Clears domain when the new role
        is not 'expert' so stale domain data cannot affect access control.
        """
        user = self.find_by_id(user_id)
        if not user:
            return None
        user.role   = role
        user.domain = domain if role == "expert" else ""
        self._save()
        return user

    def create_user(self, name: str, email: str, role: str, domain: str) -> User:
        """Creates a new user with the standard firstname_1234 password convention."""
        first = name.split()[0].lower()
        password = f"{first}_1234"
        user = User(
            user_id       = f"usr_{uuid.uuid4().hex[:6]}",
            name          = name,
            email         = email,
            role          = role,
            domain        = domain if role == "expert" else "",
            password_hash = _hash(password),
        )
        self._users.append(user)
        self._save()
        return user
