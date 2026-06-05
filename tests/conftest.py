import json
import sys
from pathlib import Path

import pytest

import decision_prover.ai.client as openrouter_client_module

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

BATTERY_PATH = REPO_ROOT / "codex-resources" / "original-project-specs" / "decision_battery.json"
PROPOSALS_PATH = REPO_ROOT / "codex-resources" / "original-project-specs" / "nl_proposals.md"


@pytest.fixture
def battery_path() -> Path:
    return BATTERY_PATH


@pytest.fixture
def proposals_path() -> Path:
    return PROPOSALS_PATH


@pytest.fixture
def battery_data(battery_path: Path) -> dict:
    return json.loads(battery_path.read_text())


@pytest.fixture(autouse=True)
def block_live_openrouter_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked_httpx_post(*args, **kwargs):
        raise AssertionError(
            "Tests must not make live OpenRouter requests. Inject a fake client or monkeypatch"
            " OpenRouterClient for explain-path tests."
        )

    monkeypatch.setattr(openrouter_client_module.httpx, "post", _blocked_httpx_post)
