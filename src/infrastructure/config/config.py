from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PERSIST_DIR: str = os.getenv("PERSIST_DIR", str(PROJECT_ROOT / "db"))

GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

API_SERVICE_NAME: str = "youtube"
API_VERSION: str = "v3"

LANG: str = os.getenv("LANG", "en")

# Proxy settings - OPTIONAL
PROXY_USER: str | None = os.getenv("PROXY_USER")
PROXY_PASS: str | None = os.getenv("PROXY_PASS")

LLM_PROVIDER: str | None = os.getenv("LLM_PROVIDER", "anthropic")
if not LLM_PROVIDER:
    raise ValueError("LLM_PROVIDER environment variable is required")

QUERY_MODEL: str | None = os.getenv("QUERY_MODEL")
if not QUERY_MODEL:
    raise ValueError("QUERY_MODEL environment variable is required")

GENERATION_MODEL: str | None = os.getenv("GENERATION_MODEL")
if not GENERATION_MODEL:
    raise ValueError("GENERATION_MODEL environment variable is required")

EMBEDDING_PROVIDER: str | None = os.getenv("EMBEDDING_PROVIDER")
if not EMBEDDING_PROVIDER:
    raise ValueError("EMBEDDING_PROVIDER environment variable is required")

EMBEDDING_MODEL: str | None = os.getenv("EMBEDDING_MODEL")
if not EMBEDDING_MODEL:
    raise ValueError("EMBEDDING_MODEL environment variable is required")


SEARCH_TYPE: str = os.getenv("SEARCH_TYPE", "similarity")
SEARCH_K: int = int(os.getenv("SEARCH_K", "2"))
ENABLE_HYBRID_SEARCH: bool = os.getenv("ENABLE_HYBRID_SEARCH", "true").lower() == "true"

MMR_DIVERSITY_LAMBDA: float = float(os.getenv("MMR_DIVERSITY_LAMBDA", "0.7"))
MMR_FETCH_K: int = int(os.getenv("MMR_FETCH_K", "20"))
