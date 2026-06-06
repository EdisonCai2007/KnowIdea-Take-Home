from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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
DEFAULT_DECISION_PROVER_LOG_ENABLED = True
DEFAULT_DECISION_PROVER_LOG_FILE = Path("logs/decision_prover.log")
DEFAULT_DECISION_PROVER_LOG_CONSOLE = True
DEFAULT_DECISION_PROVER_LOG_RAW_OPENROUTER = True


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class OpenRouterSettings:
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: float
    log_enabled: bool
    log_file: Path
    log_console: bool
    log_raw_openrouter: bool


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False

    raise ConfigurationError(
        f"{name} must be a boolean-like value (1/0, true/false), got {raw!r}."
    )


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

    log_enabled = _parse_bool_env(
        "DECISION_PROVER_LOG_ENABLED",
        DEFAULT_DECISION_PROVER_LOG_ENABLED,
    )
    log_console = _parse_bool_env(
        "DECISION_PROVER_LOG_CONSOLE",
        DEFAULT_DECISION_PROVER_LOG_CONSOLE,
    )
    log_raw_openrouter = _parse_bool_env(
        "DECISION_PROVER_LOG_RAW_OPENROUTER",
        DEFAULT_DECISION_PROVER_LOG_RAW_OPENROUTER,
    )
    log_file_raw = os.getenv(
        "DECISION_PROVER_LOG_FILE",
        str(DEFAULT_DECISION_PROVER_LOG_FILE),
    ).strip()
    if not log_file_raw:
        raise ConfigurationError("DECISION_PROVER_LOG_FILE must not be blank.")
    log_file = Path(log_file_raw)
    if not log_file.is_absolute():
        log_file = PROJECT_ROOT / log_file

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
        log_enabled=log_enabled,
        log_file=log_file,
        log_console=log_console,
        log_raw_openrouter=log_raw_openrouter,
    )
