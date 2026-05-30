import os
from dotenv import load_dotenv

load_dotenv()

# Flask session signing key — change this in production
SECRET_KEY: str = os.getenv("SECRET_KEY", "askme-dev-key-change-in-prod")

# --- Gemini ---
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-3.5-flash"

# --- Chunking ---
# How many characters per chunk and how many to repeat at boundaries for context continuity
CHUNK_SIZE: int = 512
CHUNK_OVERLAP: int = 64

# --- Access levels used across the system ---
ACCESS_LEVELS = ["public", "internal", "confidential", "restricted"]

# ─────────────────────────────────────────────────────────────────────────────
# LLM Provider switch
# Set LLM_PROVIDER=ollama in .env to run fully offline with your local GPU.
# RTX 5070 (12 GB VRAM) — recommended models (install via `ollama pull <name>`):
#   llama3.1:8b   — 4.7 GB, best balance of speed and quality
#   qwen2.5:7b    — 4.4 GB, very strong on structured / financial text
#   mistral:7b    — 4.1 GB, good reasoning
#   gemma3:12b    — 8.1 GB, highest quality that still fits comfortably
# ─────────────────────────────────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")   # "gemini" | "ollama"

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str    = os.getenv("OLLAMA_MODEL",    "llama3.1:8b")

# Cross-encoder relevance gate (hard pre-filter before calling the LLM).
# ms-marco-MiniLM scores vary too little between relevant and irrelevant queries
# on domain-specific corpora to make a reliable hard cutoff — use -20 (disabled)
# and rely on the LLM consultation prompt to say "nothing in my database" instead.
# Set a higher value (e.g. -5) only if your corpus is large enough that truly
# irrelevant queries score significantly lower than relevant ones.
RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "-20.0"))

# --- Known business domains the enricher can assign ---
KNOWN_DOMAINS = [
    "Legal",
    "Customer Service",
    "HR",
    "Finance",
    "Technology",
    "Operations",
    "Marketing",
    "Data Procurement"
    "Other",
]
