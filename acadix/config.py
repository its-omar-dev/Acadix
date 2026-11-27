"""Environment-backed application settings."""
import os


class Settings:
    @staticmethod
    def from_env():
        database_url = os.environ.get("DATABASE_URL", "").strip() or None
        if database_url and database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url and database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        return {
            "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
            "DATABASE_URL": database_url,
            "ADMIN_TOKEN": os.environ.get("ADMIN_TOKEN", ""),
            "SECRET_KEY": os.environ.get("SECRET_KEY") or os.urandom(32).hex(),
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            "SESSION_COOKIE_SECURE": os.environ.get("COOKIE_SECURE", "0") == "1",
            "MAX_CONTENT_LENGTH": 64 * 1024,
        }
