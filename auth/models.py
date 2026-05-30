from dataclasses import dataclass


@dataclass
class User:
    """
    Every field is required at construction so it is impossible to create a
    partially-initialised user that slips past access-control checks.
    domain is "" for admin and regular user roles — only experts have a
    domain so the enforcement logic can rely on a non-empty string check.
    """
    user_id:       str
    name:          str
    email:         str
    role:          str   # "user" | "expert" | "admin"
    domain:        str   # expert's domain ("Legal", "Marketing", …) or "" otherwise
    password_hash: str

    @property
    def initials(self) -> str:
        """Two-letter initials used for the avatar badge in the UI."""
        parts = self.name.split()
        return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else self.name[:2].upper()

    def to_public_dict(self) -> dict:
        """Serialises user info safe to send to the browser — no password hash."""
        return {
            "user_id": self.user_id,
            "name":    self.name,
            "email":   self.email,
            "role":    self.role,
            "domain":  self.domain,
            "initials":self.initials,
        }
