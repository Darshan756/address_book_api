from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # app
    APP_NAME: str = "Address Book API"
    DEBUG: bool = False

    # database
    DATABASE_URL: str = "sqlite+aiosqlite:///./address_book.db"

    # distance unit used in haversine search — "km" or "miles"
    DEFAULT_DISTANCE_UNIT: str = "km"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # fix: was False — env var names must match exact case
        # e.g. DATABASE_URL in .env maps to DATABASE_URL in class
        case_sensitive=True,
    )


settings = Settings()