from __future__ import annotations

import os
from dataclasses import dataclass

from .constants import PROJECT_ROOT

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is absent
    def load_dotenv(dotenv_path: os.PathLike[str] | str) -> None:
        path = os.fspath(dotenv_path)
        if not os.path.exists(path):
            return

        with open(path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue

                os.environ[key] = value.strip().strip("\"'")

DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_TIMEOUT_SECONDS = 30.0


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class OpenRouterSettings:
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: float


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def get_openrouter_settings(*, require_api_key: bool = False) -> OpenRouterSettings:
    load_environment()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or None
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL
    base_url = (
        os.getenv("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL).strip()
        or DEFAULT_OPENROUTER_BASE_URL
    ).rstrip("/")

    timeout_raw = os.getenv(
        "OPENROUTER_TIMEOUT_SECONDS",
        str(DEFAULT_OPENROUTER_TIMEOUT_SECONDS),
    ).strip()
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"OPENROUTER_TIMEOUT_SECONDS must be a positive number, got {timeout_raw!r}."
        ) from exc

    if timeout_seconds <= 0:
        raise ConfigurationError("OPENROUTER_TIMEOUT_SECONDS must be greater than zero.")

    if require_api_key and api_key is None:
        raise ConfigurationError(
            "OPENROUTER_API_KEY is required for AI explanation surfaces. Add it to .env or"
            " the process environment."
        )

    return OpenRouterSettings(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
