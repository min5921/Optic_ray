"""JSON Schema loading and user-facing validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from lidarsim.errors import ConfigFileError, ConfigValidationError, Diagnostic


def _json_path(parts: Any) -> str:
    text = ""
    for part in parts:
        if isinstance(part, int):
            text += f"[{part}]"
        elif text:
            text += f".{part}"
        else:
            text = str(part)
    return text


@dataclass(frozen=True, slots=True)
class SchemaStore:
    """Loaded project schemas with local reference resolution."""

    schema_dir: Path
    schemas: dict[str, dict[str, Any]]
    registry: Registry

    @classmethod
    def load(cls, schema_dir: Path) -> "SchemaStore":
        schema_dir = schema_dir.resolve()
        if not schema_dir.is_dir():
            raise ConfigFileError(schema_dir, "Schema directory does not exist.")

        schemas: dict[str, dict[str, Any]] = {}
        resources: list[tuple[str, Resource[Any]]] = []
        for path in sorted(schema_dir.glob("*.schema.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigFileError(path, f"Cannot read JSON schema: {exc}") from exc
            schemas[path.name] = document
            if not (schema_id := document.get("$id")):
                raise ConfigFileError(path, "JSON schema must declare an absolute $id.")
            resources.append((str(schema_id), Resource.from_contents(document)))

        if not schemas:
            raise ConfigFileError(schema_dir, "No *.schema.json files were found.")
        return cls(
            schema_dir=schema_dir,
            schemas=schemas,
            registry=Registry().with_resources(resources),
        )

    def validate(self, instance: Any, schema_name: str, *, source: str) -> None:
        try:
            schema = self.schemas[schema_name]
        except KeyError as exc:
            raise ConfigFileError(self.schema_dir / schema_name, "Requested schema is not loaded.") from exc

        validator = Draft202012Validator(
            schema,
            registry=self.registry,
            format_checker=FormatChecker(),
        )
        diagnostics: list[Diagnostic] = []
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
            path = _json_path(error.absolute_path)
            hint = None
            if error.validator == "additionalProperties":
                hint = "Remove the unknown field or update the schema intentionally. Unknown fields are rejected by default."
            elif error.validator == "required":
                hint = "Add the required field using the project manual or baseline config as a template."
            elif error.validator in {"enum", "const"}:
                hint = "Choose one of the allowed values shown in the validation message."
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path=path,
                    message=error.message,
                    hint=hint,
                )
            )
        if diagnostics:
            raise ConfigValidationError(diagnostics)
