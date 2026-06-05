from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
DEFAULT_BATTERY_PATH = (
    PROJECT_ROOT / "codex-resources" / "original-project-specs" / "decision_battery.json"
)
DEFAULT_PROPOSALS_PATH = (
    PROJECT_ROOT / "codex-resources" / "original-project-specs" / "nl_proposals.md"
)

