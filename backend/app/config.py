"""Explicit runtime settings; importing this module never reads private configuration."""
from dataclasses import dataclass, field
import os
from urllib.parse import urlparse

@dataclass(frozen=True)
class HttpSettings:
    trusted_origins: tuple[str, ...] = ("http://127.0.0.1:18080",)
    secure_cookie: bool = True
    allow_loopback_http: bool = False
    upload_limit_bytes: int = 10 * 1024 * 1024
    request_timeout_seconds: int = 180
    frontend_dist: str = "frontend/dist"
    def __post_init__(self):
        if self.upload_limit_bytes < 1 or self.request_timeout_seconds < 1:
            raise ValueError("Positive limits required")
        if not self.secure_cookie and (not self.allow_loopback_http or any(
            urlparse(x).scheme != "http" or urlparse(x).hostname not in ("localhost", "127.0.0.1", "::1")
            for x in self.trusted_origins)):
            raise ValueError("Insecure cookies require explicit loopback HTTP mode")

@dataclass(frozen=True)
class RuntimeSettings:
    http: HttpSettings
    secret: str = field(repr=False)
    database_url: str = field(repr=False, default="")
    restricted_database_url: str = field(repr=False, default="")
    qdrant_url: str = ""
    qdrant_key: str = field(repr=False, default="")
    collection: str = "relex"
    model_url: str = ""
    model_name: str = ""
    model_key: str = field(repr=False, default="")
    privacy_model_url: str = ""
    privacy_model_name: str = ""
    privacy_model_key: str = field(repr=False, default="")
    embedding_url: str = ""
    embedding_model: str = ""
    embedding_key: str = field(repr=False, default="")
    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(override=False)
        e = os.environ
        secret = e.get("RELEX_SESSION_SECRET", "")
        if len(secret) < 32:
            raise ValueError("RELEX_SESSION_SECRET requires at least 32 characters")
        loopback = e.get("RELEX_LOOPBACK_HTTP") == "1"
        model_url = e.get("RELEX_MODEL_BASE_URL", "https://api.openai.com/v1")
        model_name = e.get("RELEX_MODEL_NAME", "")
        model_key = e.get("RELEX_MODEL_API_KEY") or e.get("OPENAI_API_KEY", "")
        return cls(
            http=HttpSettings(tuple(e.get("RELEX_TRUSTED_ORIGINS", "http://127.0.0.1:18080").split(",")),
                not loopback, loopback, int(e.get("RELEX_UPLOAD_LIMIT_BYTES", "10485760")),
                int(e.get("RELEX_REQUEST_TIMEOUT_SECONDS", "180")),
                e.get("RELEX_FRONTEND_DIST", "frontend/dist")),
            secret=secret, database_url=e.get("RELEX_DATABASE_URL", ""),
            restricted_database_url=e.get("RELEX_RESTRICTED_DATABASE_URL", ""),
            qdrant_url=e.get("RELEX_QDRANT_URL", ""), qdrant_key=e.get("RELEX_QDRANT_API_KEY", ""),
            collection=e.get("RELEX_QDRANT_COLLECTION", "relex"),
            model_url=model_url,
            model_name=model_name,
            model_key=model_key,
            privacy_model_url=e.get("RELEX_PRIVACY_MODEL_BASE_URL") or model_url,
            privacy_model_name=e.get("RELEX_PRIVACY_MODEL_NAME") or model_name,
            privacy_model_key=e.get("RELEX_PRIVACY_MODEL_API_KEY") or model_key,
            embedding_url=e.get("RELEX_EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
            embedding_model=e.get("RELEX_EMBEDDING_MODEL", ""),
            embedding_key=e.get("RELEX_EMBEDDING_API_KEY") or e.get("OPENAI_API_KEY", ""))
