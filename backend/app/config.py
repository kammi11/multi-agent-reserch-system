"""
ResearchPilot AI — configuration.

Every external provider (LLM, search, embeddings) is selected here via
environment variables so the system runs free-first (local/offline) by
default and can be pointed at real paid/free-tier services without any
code changes.
"""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ResearchPilot AI"
    tagline: str = "An Agentic AI Research System for Evidence-Based Answers"

    # --- LLM provider: ollama | openrouter | offline ------------------
    # "offline" is a deterministic, extractive, no-network synthesizer.
    # It is NOT a simulation of an LLM's output — it is a real, separate
    # implementation that produces genuinely computed (if less fluent)
    # summaries/plans, used so the system can run with zero paid/network
    # services and so this sandbox can demonstrate a real end-to-end run.
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    ollama_base_url: str = "http://localhost:11434"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Search provider: tavily | brave | duckduckgo | offline -------
    # "offline" searches a small bundled local corpus (data/corpus/) —
    # real retrieval + real scoring, just not the live internet.
    search_provider: str = "duckduckgo"
    tavily_api_key: str = ""
    brave_api_key: str = ""

    # --- Embeddings: local (TF-IDF, always available, zero network) or
    # sentence_transformers (better quality, requires extra install) ---
    embedding_provider: str = "local"
    embedding_model: str = "tfidf"

    # --- Research control ---------------------------------------------
    max_research_iterations: int = 3
    max_sources_per_query: int = 5
    max_queries_per_iteration: int = 4
    request_timeout_seconds: int = 15
    max_document_chars: int = 20000

    # --- Storage ---------------------------------------------------------
    database_url: str = "sqlite:///./data/researchpilot.db"

    # --- Server ----------------------------------------------------------
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
