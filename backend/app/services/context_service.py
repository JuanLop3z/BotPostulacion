import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from app.schemas import ApplicationRules, ContextBundle, JobPreferences

_MAX_CONTEXT_BYTES = 100000


class ContextError(ValueError):
    pass


class _StrictLoader(yaml.SafeLoader):
    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            raise ContextError("No se permiten aliases YAML en la configuración.")
        depth = getattr(self, "_context_depth", 0)
        if depth > 30:
            raise ContextError("La configuración YAML tiene demasiados niveles.")
        self._context_depth = depth + 1
        try:
            return super().compose_node(parent, index)
        finally:
            self._context_depth = depth

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in result:
                    raise ContextError("La configuración contiene claves YAML duplicadas.")
                result[key] = self.construct_object(value_node, deep=deep)
            except TypeError as exc:
                raise ContextError("Las claves YAML deben ser valores escalares.") from exc
        return result


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    if path.stat().st_size > _MAX_CONTEXT_BYTES:
        raise ContextError("Un archivo de contexto supera el tamaño permitido.")
    return path.read_text(encoding="utf-8-sig")


def _mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(_read(path), Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise ContextError(f"YAML inválido en {path.name}.") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ContextError(f"{path.name} debe contener un objeto YAML.")
    return value


def load_context(directory: Path) -> ContextBundle:
    return ContextBundle(
        candidate_context=_read(directory / "candidate_context.md"),
        custom_instructions=_read(directory / "custom_instructions.md"),
        preferences=JobPreferences.model_validate(_mapping(directory / "job_preferences.yaml")),
        rules=ApplicationRules.model_validate(_mapping(directory / "application_rules.yaml")),
    )


def save_context(directory: Path, bundle: ContextBundle) -> None:
    """Export validated values. Runtime versions are persisted transactionally by the API."""
    checked = ContextBundle.model_validate(bundle.model_dump())
    directory.mkdir(parents=True, exist_ok=True)
    content = {
        "candidate_context.md": checked.candidate_context,
        "custom_instructions.md": checked.custom_instructions,
        "job_preferences.yaml": yaml.safe_dump(
            checked.preferences.model_dump(), allow_unicode=True, sort_keys=False
        ),
        "application_rules.yaml": yaml.safe_dump(
            checked.rules.model_dump(), allow_unicode=True, sort_keys=False
        ),
    }
    for filename, value in content.items():
        descriptor, temporary = tempfile.mkstemp(prefix=".context-", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(value)
            os.replace(temporary, directory / filename)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
