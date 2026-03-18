from pydantic_settings import BaseSettings
from pydantic import validator

class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    groq_api_key: str

    @validator('supabase_url')
    def url_must_be_https(cls, v):
        if not v.startswith('https://'):
            raise ValueError('Supabase URL must use HTTPS')
        return v

    @validator('groq_api_key', 'supabase_key', 'supabase_service_key')
    def keys_not_empty(cls, v):
        if not v or len(v) < 10:
            raise ValueError('API key appears invalid')
        return v

    class Config:
        env_file = ".env"

settings = Settings()