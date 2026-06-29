from __future__ import annotations

from pathlib import Path

from lidarsim.config import load_project
from lidarsim.visualization import render_placement_view


def test_headless_placement_view_writes_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    output_path = tmp_path / "placement.png"

    result = render_placement_view(project, output_path, dpi=72)

    assert result == output_path.resolve()
    payload = output_path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 10_000
