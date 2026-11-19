"""Application settings. Every configurable value comes from environment variables (or .env).

Each field below maps to an upper-case env var (`database_url` <- DATABASE_URL). See
backend/.env.example for the documented list. Settings are read once per process and cached,
so restart the server after editing .env.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"
MIN_SECRET_LENGTH = 32  # `fintrack gen-keys` produces 64 characters


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    # Database: SQLite by default; any SQLAlchemy URL works (e.g. postgresql+psycopg://...).
    database_url: str = "sqlite:///./data/fintrack.db"

    # Secrets. Generate real values with `fintrack gen-keys`.
    secret_key: str = INSECURE_DEFAULT_SECRET
    encryption_key: str = ""  # Fernet key used to encrypt provider credentials at rest

    # Comma-separated origins allowed to call the API cross-origin (only needed when the
    # frontend is hosted on a different domain than the API).
    cors_origins: str = ""

    # Session cookie
    cookie_name: str = "fintrack_session"
    cookie_secure: bool = False  # set true when served over HTTPS
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_days: int = 30  # idle sessions end after this; each visit extends them
    session_max_days: int = 90  # ...but no session lives longer than this, active or not

    # Password hashing (argon2) uses ~64 MiB of RAM per hash. Capping how many run at once keeps
    # a burst of logins from exhausting memory on small machines (a Raspberry Pi, a 1 GB VM).
    password_hash_concurrency: int = 2

    # The very first account can always be created; after that this controls open sign-ups.
    allow_signup: bool = True

    # Sync
    run_scheduler: bool = True
    sync_interval_hours: int = 6
    sync_cooldown_minutes: int = 15  # minimum gap between "Sync now" clicks per connection
    initial_sync_days: int = 90  # history requested on the first sync
    sync_overlap_days: int = 14  # re-fetch this far back each sync to catch late-posting items
    # "Sync now" runs allowed per connection per 24 h. With the 4 scheduled syncs a day this stays
    # under SimpleFIN's ~24 requests/day/connection guideline.
    sync_manual_daily_limit: int = 12

    # The only hosts FinTrack will contact for SimpleFIN (a domain also allows its subdomains).
    # Stops a pasted setup token or access URL from making the server call arbitrary addresses.
    simplefin_allowed_hosts: str = "simplefin.org"

    @field_validator("secret_key")
    @classmethod
    def _blank_secret_uses_default(cls, value: str) -> str:
        # An empty SECRET_KEY= line in .env falls back to the default (and logs a warning).
        return value or INSECURE_DEFAULT_SECRET

    @field_validator("cors_origins")
    @classmethod
    def _exact_origins_only(cls, value: str) -> str:
        """Only exact origins like https://fintrack.example.com.

        "*" is refused: with credentials allowed, the CORS middleware would answer *any* website
        with that website's own origin, letting every page you visit read and change your data.
        """
        for origin in (o.strip() for o in value.split(",")):
            if not origin:
                continue
            scheme, sep, rest = origin.partition("://")
            if (
                "*" in origin
                or not sep
                or scheme not in ("http", "https")
                or not rest
                or "/" in rest.rstrip("/")
            ):
                raise ValueError(
                    f"CORS_ORIGINS entry {origin!r} isn't an exact origin. List full origins "
                    "such as https://fintrack.example.com, comma-separated; '*' is not allowed."
                )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def simplefin_host_list(self) -> list[str]:
        return [
            h.strip().lower().rstrip(".")
            for h in self.simplefin_allowed_hosts.split(",")
            if h.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        """Over HTTPS the cookie gets the __Host- prefix: browsers then accept it only with
        Secure, Path=/ and no Domain, so it's bound to exactly this host and can't be set or
        overwritten by other sites or subdomains. (Browsers still send cookies to other *ports* of
        the same host, so give FinTrack its own hostname; see docs/architecture.md#security.)"""
        if self.cookie_secure and not self.cookie_name.startswith("__Host-"):
            return f"__Host-{self.cookie_name}"
        return self.cookie_name


def check_runtime_settings(settings: Settings) -> None:
    """Refuse to run in production with the published default or a short SECRET_KEY.

    Called at startup by app/main.py and app/worker.py. Development and tests only get a warning
    (logged by main.py), so a fresh checkout still starts.
    """
    if not settings.is_production:
        return
    if settings.secret_key == INSECURE_DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY is not set. Run `fintrack gen-keys` (Docker: "
            "`docker compose run --rm backend fintrack gen-keys`) and paste the values into "
            "backend/.env."
        )
    if len(settings.secret_key) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY is too short ({len(settings.secret_key)} characters; at least "
            f"{MIN_SECRET_LENGTH} required). Generate one with `fintrack gen-keys`."
        )


@lru_cache
def get_settings() -> Settings:
    """The process-wide settings. Tests clear the cache to apply their own env vars."""
    return Settings()
