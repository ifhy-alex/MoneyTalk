from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno / `.env`. Los secretos solo viven aquí."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://moneytalk:devlocal@127.0.0.1:5433/moneytalk"
    app_timezone: str = "America/Costa_Rica"
    log_level: str = "INFO"
    data_dir: Path = Path("data")

    gmail_credentials_file: Path = Path("data/gmail_credentials.json")
    gmail_token_file: Path = Path("data/gmail_token.json")
    # Vacío = buscar por remitentes de bancos de CR (recomendado). Con valor = solo esa etiqueta.
    gmail_label: str = ""
    # Dominios adicionales de remitentes, separados por coma.
    gmail_extra_senders: str = ""
    # Primera sincronización: cuántos días hacia atrás leer.
    gmail_initial_days: int = 120
    # Carpeta vigilada: cualquier PDF que dejés aquí se importa solo.
    inbox_dir: Path = Path("data/inbox")
    # Contraseñas de PDFs protegidos (separadas por coma). Opcional; solo en .env.
    statement_pdf_passwords: str = ""

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"

    bccr_email: str = ""
    bccr_token: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    market_provider: str = "yfinance"
    fmp_api_key: str = ""
    alphavantage_api_key: str = ""
    sec_user_agent: str = "MoneyTalk contacto@example.com"
    market_cache_ttl_hours: int = Field(default=12, ge=0)

    cors_origins: list[str] = ["http://localhost:5173"]

    # Modo escritorio (ejecutable): la API también sirve el frontend compilado.
    desktop_mode: bool = False
    static_dir: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
