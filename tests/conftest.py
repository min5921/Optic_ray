from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def copied_project(tmp_path: Path, project_root: Path) -> Path:
    for name in ("schemas", "configs", "catalog", "assets"):
        shutil.copytree(project_root / name, tmp_path / name)
    return tmp_path / "configs" / "project.yaml"
