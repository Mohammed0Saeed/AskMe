"""
Runtime LLM provider configuration.

The active provider and Anthropic API key are stored in
data/provider_config.json, which is gitignored so secrets never enter
version control.  On startup the file is loaded (if it exists) to
restore the last admin-chosen config across server restarts.
"""
import json
import os

_CONFIG_PATH = "data/provider_config.json"

_config: dict = {}


def load() -> dict:
    """Load persisted config from disk; called once at app startup."""
    global _config
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                _config = json.load(f)
        except (json.JSONDecodeError, OSError):
            _config = {}
    return _config


def get() -> dict:
    """Return the current in-memory config."""
    return _config


def save(provider: str, anthropic_api_key: str = "", anthropic_model: str = "claude-sonnet-4-6") -> dict:
    """Persist a new provider choice and return the updated config."""
    global _config
    _config = {
        "provider":          provider,
        "anthropic_api_key": anthropic_api_key,
        "anthropic_model":   anthropic_model,
    }
    os.makedirs("data", exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_config, f)
    return _config


def active_provider() -> str:
    """Returns the currently active provider name."""
    from config import LLM_PROVIDER
    return _config.get("provider") or LLM_PROVIDER


def has_anthropic_key() -> bool:
    return bool(_config.get("anthropic_api_key", "").strip())
