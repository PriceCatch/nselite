"""REFERENCE.md must list every report key, so users see all options."""

from pathlib import Path

from nselite import ReportKey
from nselite.reports import SPECS

DOC = (Path(__file__).parents[2] / "REFERENCE.md").read_text()


def test_every_report_key_is_documented() -> None:
    for key in ReportKey:
        row = f"| `{key.name}` | `{key.value}` | {SPECS[key].segment} |"
        assert row in DOC, f"REFERENCE.md is missing {key.name}"
