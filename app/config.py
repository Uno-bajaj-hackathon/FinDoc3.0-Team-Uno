from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    openai_key: str = Field(..., env="OPENAI_API_KEY")
    openai_base_url: str = Field("https://openrouter.ai/api/v1", env="OPENAI_BASE_URL")
    bearer: str = Field(..., env="TEAM_BEARER")
    qdrant_url: str = Field(..., env="QDRANT_URL")
    qdrant_api_key: str = Field(None, env="QDRANT_API_KEY")

settings = Settings(_env_file=".env", _env_file_encoding="utf-8")
