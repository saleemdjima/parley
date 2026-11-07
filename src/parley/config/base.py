from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Credentials
    google_api_key: str = ""

    # LLM (provider-switchable via LangChain init_chat_model)
    llm_provider: str = "google_genai"
    llm_model: str = "gemini-2.0-flash"

    # Embeddings / RAG
    embeddings_provider: str = "google"
    embeddings_model_google: str = "models/gemini-embedding-001"
    embeddings_model_hf: str = "sentence-transformers/all-MiniLM-L6-v2"
    docs_dir: str = "data/docs"
    chroma_dir: str = "data/chroma"
    chroma_collection: str = "tlc_docs"
    # Vector-store seam: "local" uses a persist_directory (dev / ephemeral demo);
    # "server" connects to a Chroma HTTP server (stateless app, external state).
    chroma_mode: str = "local"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_k: int = 4

    # Query engine
    engine: str = "duckdb"
    parquet_path: str = "data/yellow_tripdata_2024-01.parquet"
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "default"
    clickhouse_table: str = "trips"

    # Guardrails
    max_limit: int = 1000
    max_question_length: int = 500

    # Slack connector
    slack_bot_token: str = ""
    slack_app_token: str = ""

    # API
    cors_allow_origins: str = "*"
    api_key: str = ""  # guards write endpoints (e.g. POST /documents); empty = locked


settings = Settings()

