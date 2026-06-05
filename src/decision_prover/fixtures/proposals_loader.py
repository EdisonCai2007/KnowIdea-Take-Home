from __future__ import annotations

import re
from pathlib import Path

from .errors import FixtureLoadError
from ..proposals import ProposalFixture, ProposalPrompt

VALID_HEADING = re.compile(r"^\*\*(P\d+)\.\*\*$")


def load_proposals_fixture(input_path: str | Path) -> ProposalFixture:
    source_path = Path(input_path)
    try:
        text = source_path.read_text()
    except FileNotFoundError as exc:
        raise FixtureLoadError(source_path, [f"{source_path}: file not found"]) from exc

    lines = text.splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), source_path.stem)

    heading_positions: list[tuple[int, str]] = []
    errors: list[str] = []
    seen_ids: dict[str, int] = {}

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not (stripped.startswith("**") and stripped.endswith("**")):
            continue

        match = VALID_HEADING.match(stripped)
        if not match:
            errors.append(
                f"{source_path}:line {line_number}: invalid proposal heading '{stripped}'"
            )
            continue

        proposal_id = match.group(1)
        if proposal_id in seen_ids:
            errors.append(
                f"{source_path}:line {line_number}: duplicate proposal id '{proposal_id}' "
                f"(first defined at line {seen_ids[proposal_id]})"
            )
            continue

        seen_ids[proposal_id] = line_number
        heading_positions.append((line_number - 1, proposal_id))

    if not heading_positions and not errors:
        errors.append(f"{source_path}: no proposal headings found")

    proposals: list[ProposalPrompt] = []
    for idx, (start_index, proposal_id) in enumerate(heading_positions):
        end_index = (
            heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(lines)
        )
        block = lines[start_index + 1 : end_index]
        quote_lines = [line.split(">", 1)[1].strip() for line in block if line.lstrip().startswith(">")]
        if not quote_lines:
            errors.append(
                f"{source_path}:line {start_index + 1}: proposal '{proposal_id}' is missing quoted text"
            )
            continue

        proposal_text = "\n".join(quote_lines).strip()
        proposals.append(ProposalPrompt(id=proposal_id, text=proposal_text))

    if errors:
        raise FixtureLoadError(source_path, errors)

    return ProposalFixture(title=title, proposals=proposals)

