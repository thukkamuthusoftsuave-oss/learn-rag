"""Single source of truth for paths, model names and prompts.

Every value can be overridden with an environment variable (read from the
process environment or a local ``.env`` file), so the same code runs from a
developer machine, a container or a test run without edits.  Relative path
overrides are resolved against the project root, never the current working
directory, so the CLI behaves identically wherever it is invoked from.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


def _env_path(name: str, default: str) -> Path:
    """Resolves a path setting, anchoring relative values at the project root.

    Args:
        name: Environment variable to read.
        default: Fallback value used when the variable is unset.

    Returns:
        An absolute ``Path``.
    """
    raw = Path(os.getenv(name, default)).expanduser()
    return raw if raw.is_absolute() else (PROJECT_ROOT / raw).resolve()


def _env_bool(name: str, default: bool) -> bool:
    """Reads a boolean setting written as ``1/true/yes/on`` (case-insensitive)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Reads an integer setting, falling back to ``default`` when unparseable."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Filesystem layout -----------------------------------------------------
# chroma_db/ and storage/ are derived artifacts, rebuilt by `ingest`.
# var/ holds runtime state (the trace log); reports/ holds generated reports.
DATA_DIR = _env_path("RAG_DATA_DIR", "data")
CHROMA_DIR = _env_path("RAG_CHROMA_DIR", "chroma_db")
STORAGE_DIR = _env_path("RAG_STORAGE_DIR", "storage")
VAR_DIR = _env_path("RAG_VAR_DIR", "var")
REPORTS_DIR = _env_path("RAG_REPORTS_DIR", "reports")
TRACE_FILE = _env_path("RAG_TRACE_FILE", "var/traces.jsonl")
STATIC_DIR = PACKAGE_ROOT / "web" / "static"

# --- Vector store backend --------------------------------------------------
# "local" keeps embeddings in CHROMA_DIR; "cloud" stores them in a hosted
# Chroma Cloud database. See policy_rag.vector_store for what each one means -
# note the docstore in STORAGE_DIR stays on disk either way.
VECTOR_BACKEND = os.getenv("RAG_VECTOR_BACKEND", "local")
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY", "")
CHROMA_TENANT = os.getenv("CHROMA_TENANT", "")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "")

# --- Models and index ------------------------------------------------------
COLLECTION_NAME = os.getenv("RAG_COLLECTION", "hr_policies")
EMBED_MODEL_NAME = os.getenv("RAG_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
# OpenRouter exposes providers through an OpenAI-compatible endpoint.  A model
# slug is always ``provider/model`` and can be changed without touching code.
LLM_MODEL_NAME = os.getenv("RAG_LLM_MODEL", "google/gemini-2.5-flash-lite")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_CONTEXT_WINDOW = _env_int("RAG_LLM_CONTEXT_WINDOW", 32_768)
LLM_MAX_TOKENS = _env_int("RAG_LLM_MAX_TOKENS", 512)
CHUNK_SIZES = [512, 128]
CHUNK_OVERLAP = 20

# --- Retrieval defaults ----------------------------------------------------
DEFAULT_TOP_K = _env_int("RAG_TOP_K", 5)
# Hybrid (BM25 + vector, RRF-fused) retrieval is the shipped default because
# it wins where users actually are: on the eight region-explicit questions it
# takes hit-rate@1 from 0.875 to 1.000 (MRR 0.938 -> 1.000). It is not free -
# on the exact-term set it moved a section-number question from rank 1 to
# rank 2 (MRR 0.778 -> 0.611, n=3), leaving overall MRR unchanged. Re-measure
# with `policy-rag eval retrieval` after any index change before trusting
# either number; both sets are small enough that one question moves them.
DEFAULT_HYBRID = _env_bool("RAG_HYBRID", True)
# History turns fed to the follow-up condenser (user+assistant pairs).
MAX_HISTORY_TURNS = _env_int("RAG_MAX_HISTORY_TURNS", 6)

# --- Evaluation pacing -----------------------------------------------------
# The answer-quality suite fires one LLM call per question. Keep this low for
# paid OpenRouter models, but raise it when the selected model/key has a lower
# request-per-minute ceiling. A rate limit is never an answer-quality result.
EVAL_PAUSE_SECONDS = float(os.getenv("RAG_EVAL_PAUSE_SECONDS", "2"))
EVAL_RETRIES = _env_int("RAG_EVAL_RETRIES", 2)

# --- Server ----------------------------------------------------------------
API_HOST = os.getenv("RAG_HOST", "0.0.0.0")
API_PORT = _env_int("RAG_PORT", 8000)

# The admin console can rebuild the index and spend LLM calls, and it is not
# authenticated. On by default because this runs on a laptop; turn it off
# before exposing the server to anyone else.
ADMIN_ENABLED = _env_bool("RAG_ADMIN_ENABLED", True)

# --- Prompts ---------------------------------------------------------------
# Must stay byte-identical to the refusal sentence inside QA_PROMPT_TEMPLATE:
# refusal detection is a substring check against this constant.
REFUSAL_SENTINEL = "I'm sorry, I cannot answer that question based on the provided documents."

QA_PROMPT_TEMPLATE = (
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given the context information and not prior knowledge, answer the query.\n"
    f"If the answer is not in the context, say exactly: '{REFUSAL_SENTINEL}'\n"
    "When you provide an answer, you MUST append a citation pointing to the chunk_id and source_file. "
    "Format: [[Policy Section]](chunk_id:SOURCE_FILE_NAME)\n"
    "Query: {query_str}\n"
    "Answer: "
)

# Follow-ups such as "what about the UK?" are meaningless to a retriever on
# their own, so they are rewritten into standalone questions before retrieval.
CONDENSE_PROMPT_TEMPLATE = (
    "Rewrite the follow-up question into a standalone question that can be "
    "understood without the conversation.\n"
    "Keep every concrete detail the user gave earlier (region, employee type, "
    "years of service, section numbers). Do not answer the question. Return "
    "only the rewritten question.\n\n"
    "Conversation:\n"
    "{chat_history}\n\n"
    "Follow-up question: {question}\n"
    "Standalone question: "
)

REGIONS = ["NA", "US", "UK", "EMEA", "APAC", "LATAM"]


def openrouter_api_key() -> str:
    """Returns the configured OpenRouter API key, or an empty string when unset."""
    return os.getenv("OPENROUTER_API_KEY", "")


def ensure_runtime_dirs() -> None:
    """Creates the writable directories the app expects (``var/``, ``reports/``)."""
    VAR_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
