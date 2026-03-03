from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Local Ollama
    OLLAMA_LOCAL_URL: str = "http://ollama:11434"
    OLLAMA_MODEL_PREPROCESS: str = "qwen2.5:7b"
    OLLAMA_MODEL_CLASSIFY: str = "qwen2.5:7b"
    OLLAMA_MODEL_CHAT: str = "qwen2.5:14b"
    OLLAMA_MODEL_EMBED: str = "nomic-embed-text"

    # Cloud Ollama
    OLLAMA_CLOUD_URL: str = "https://api.ollama.com"
    OLLAMA_CLOUD_API_KEY: str = ""
    OLLAMA_MODEL_SEGMENT: str = "deepseek-v3"
    OLLAMA_MODEL_REPORT: str = "deepseek-v3"
    OLLAMA_MODEL_SYNTHESIZE: str = "deepseek-v3"
    OLLAMA_MODEL_TITLE: str = "deepseek-v3"
    OLLAMA_MODEL_EDUCATE: str = "deepseek-v3"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/sentinel"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@db:5432/sentinel"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # LangFuse (optional)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://langfuse:3000"

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"

    def get_model_for_task(self, task: str) -> str:
        mapping = {
            "preprocess": self.OLLAMA_MODEL_PREPROCESS,
            "classify": self.OLLAMA_MODEL_CLASSIFY,
            "classify_escalation": self.OLLAMA_MODEL_SEGMENT,  # cloud model
            "segment": self.OLLAMA_MODEL_SEGMENT,
            "report": self.OLLAMA_MODEL_REPORT,
            "synthesize": self.OLLAMA_MODEL_SYNTHESIZE,
            "title": self.OLLAMA_MODEL_TITLE,
            "educate": self.OLLAMA_MODEL_EDUCATE,
            "chat": self.OLLAMA_MODEL_CHAT,
            "embed": self.OLLAMA_MODEL_EMBED,
        }
        return mapping.get(task, self.OLLAMA_MODEL_REPORT)


settings = Settings()
