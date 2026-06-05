from pathlib import Path

import pytest

from decision_prover.fixtures import FixtureLoadError, load_proposals_fixture


def test_proposals_fixture_parses_all_items(proposals_path: Path) -> None:
    fixture = load_proposals_fixture(proposals_path)

    assert fixture.title == "Natural-Language Proposals — Formalization Set"
    assert len(fixture.proposals) == 6
    assert fixture.proposals[0].id == "P1"
    assert "salespeople" in fixture.proposals[0].text


def test_invalid_proposal_heading_is_rejected(tmp_path: Path) -> None:
    content = """# Example Proposals

**Proposal 1**
> This heading is malformed.
"""
    path = tmp_path / "invalid_heading.md"
    path.write_text(content)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_proposals_fixture(path)

    assert "invalid proposal heading" in str(exc_info.value)


def test_missing_proposal_quote_is_rejected(tmp_path: Path) -> None:
    content = """# Example Proposals

**P1.**
This body is missing the quote marker.
"""
    path = tmp_path / "missing_quote.md"
    path.write_text(content)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_proposals_fixture(path)

    assert "missing quoted text" in str(exc_info.value)

