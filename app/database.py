from supabase import create_client, Client
from app.config import settings
from functools import lru_cache

@lru_cache(maxsize=1)
def get_admin_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)

def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)

def get_authenticated_client(token: str) -> Client:
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(token)
    return client