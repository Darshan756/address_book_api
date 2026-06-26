from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    APP_NAME: str = "Address Book API"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite+aiosqlite:///./address_book.db"
    DEFAULT_DISTANCE_UNIT: str = "km" 
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",case_sensitive=False)       

settings = Settings()