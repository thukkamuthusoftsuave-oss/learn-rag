"""Central Configuration for Enterprise Policy Assistant Backend."""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseModel):
    """Application settings with environment variable fallbacks."""
    app_name: str = "Enterprise Policy Assistant (HR-207)"
    version: str = "2.0.0"
    debug: bool = Field(default=False)
    
    # Paths
    base_dir: Path = BASE_DIR
    corpus_dir: Path = BASE_DIR / "data_and_benchmarks" / "files_to_learn" / "synthetic_corpus"
    chroma_db_dir: Path = BASE_DIR / "application" / "backend" / "storage" / "chroma_db"
    traces_file: Path = BASE_DIR / "application" / "backend" / "storage" / "traces.jsonl"
    
    # Embedding & Retrieval
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    default_top_k: int = 5
    rrf_k: int = 60
    cache_max_size: int = 1024
    
    # LLM Settings
    openrouter_api_key: str = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    default_llm_model: str = Field(default_factory=lambda: os.getenv("RAG_MODEL", "google/gemini-flash-1.5"))
    llm_temperature: float = 0.0
    llm_max_tokens: int = 512
    
    # Agent & Policy Bounds
    max_agent_laps: int = 5
    # The highest legitimate policy cap in HR-207 is 20 days (US Senior)
    max_allowed_vacation_carryover: int = 20


settings = Settings()
