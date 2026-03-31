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
    
    # Base URL for email links
    base_url: str = "https://yminternationalbeautyacademy.com"
    
    # Email SMTP Configuration
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_use_tls: bool = True
    email_use_ssl: bool = False
    email_username: str = ""
    email_password: str = ""
    email_from_name: str = "YM Beauty Academy"
    email_from_address: str = "noreply@yminternationalbeautyacademy.com"
    email_reply_to: str = "support@yminternationalbeautyacademy.com"
    email_max_retries: int = 3
    email_timeout: int = 30
    email_debug: bool = False  # Log emails instead of sending in development
    
    # OpenRouter Configuration
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    
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
