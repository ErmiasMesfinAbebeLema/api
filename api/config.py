from functools import lru_cache
import json
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = "postgresql+asyncpg://root:root@database_postgres:5432/db1010"
    
    # CORS - accept both list and string formats
    cors_origins: list = ["https://yminternationalbeautyacademy.com", "http://localhost:3000"]
    
    # JWT Authentication
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    
    # Development
    debug: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse CORS_ORIGINS if it's a string
        if isinstance(self.cors_origins, str):
            try:
                self.cors_origins = json.loads(self.cors_origins)
            except json.JSONDecodeError:
                # If it's not valid JSON, split by comma
                self.cors_origins = [origin.strip() for origin in self.cors_origins.split(',')]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
