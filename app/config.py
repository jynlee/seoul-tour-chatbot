"""환경변수(.env) 로딩과 검증."""
import os
from dataclasses import dataclass
from typing import Mapping, Sequence

REQUIRED_SERVER = ("OPENSEARCH_USER", "OPENSEARCH_PASSWORD", "MYSQL_USER", "MYSQL_PASSWORD")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    tour_api_key: str = ""
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_user: str = ""
    opensearch_password: str = ""
    opensearch_index: str = "seoul-tour-v3"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"
    embed_model: str = "jhgan/ko-sroberta-multitask"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_db: str = "seoul_tour"


def load_settings(env: Mapping[str, str] | None = None, required: Sequence[str] = REQUIRED_SERVER) -> Settings:
    if env is None:
        from dotenv import load_dotenv

        load_dotenv()
        env = os.environ

    missing = [name for name in required if not env.get(name, "").strip()]
    if missing:
        raise ConfigError(f".env에 필수 값이 비어 있어요: {', '.join(missing)}")

    values = {}
    for field, default in Settings.__dataclass_fields__.items():
        raw = env.get(field.upper(), "").strip()
        if raw:
            values[field] = int(raw) if isinstance(default.default, int) else raw
    return Settings(**values)
