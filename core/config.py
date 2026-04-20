import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # --- Project Info ---
    PROJECT_NAME: str = "BodhCS"
    API_V1_STR: str = "/api/v1"
    
    # --- Supabase ---
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    
    # --- Groq ---
    GROQ_API_KEY: str
    
    # --- Redis (Upstash) ---
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str
    
    # --- Firebase ---
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    
    @property
    def firebase_service_account_path_absolute(self) -> str:
        if os.path.isabs(self.FIREBASE_SERVICE_ACCOUNT_PATH):
            return self.FIREBASE_SERVICE_ACCOUNT_PATH
        # Resolve relative to the backend directory (parent of core/)
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(backend_dir, self.FIREBASE_SERVICE_ACCOUNT_PATH)
    
    # --- Razorpay ---
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    
    # --- Langfuse ---
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), 
        case_sensitive=True, 
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
