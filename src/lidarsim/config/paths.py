"""Project-relative path discovery shared by config, CLI and UI variants."""

from __future__ import annotations

from pathlib import Path

from lidarsim.errors import ConfigFileError


def find_project_root(project_path: str | Path) -> Path:
    """Find the nearest ancestor containing the repository schema contract."""

    path = Path(project_path).resolve()
    for candidate in path.parents:
        if (candidate / "schemas" / "project.schema.json").is_file():
            return candidate
    raise ConfigFileError(
        path,
        "schemas/project.schema.json을 포함한 project root를 상위 directory에서 찾을 수 없습니다.",
    )


def schema_directory_for_project(project_path: str | Path) -> Path:
    """Return the schema directory governing a project YAML."""

    return find_project_root(project_path) / "schemas"


__all__ = ["find_project_root", "schema_directory_for_project"]
