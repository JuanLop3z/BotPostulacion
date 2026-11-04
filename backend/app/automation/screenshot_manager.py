"""Store optional evidence after masking potentially sensitive form values."""

from pathlib import Path
from typing import Any


def redacted_screenshot(page: Any, directory: Path, identifier: str) -> Path:
    # Fixed filename alphabet keeps the storage path under the configured root.
    if not identifier or not all(char.isascii() and (char.isalnum() or char in "-_") for char in identifier):
        raise ValueError("Identificador de captura inválido.")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory.resolve() / f"{identifier}.png"
    page.screenshot(
        path=str(target),
        mask=[page.locator("input, textarea, select, [data-private]")],
        full_page=False,
    )
    return target
