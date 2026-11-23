"""Detect installed agents and agent layers already present in a vault."""
from __future__ import annotations

from pathlib import Path

INSTALLED = {
    "codex": (".codex",),
    "claude": (".claude",),
    "cursor": (".cursor",),
    "gemini": (".gemini",),
    "antigravity": (".gemini/antigravity",),
    "zcode": (".zcode",),
    "windsurf": (".windsurf",),
}
SKIP_LAYERS = {"archive", "conversations", ".gitkeep"}


def detect_installed(home=None):
    root = Path(home).expanduser() if home else Path.home()
    names = [
        name for name, markers in INSTALLED.items() if any((root / marker).exists() for marker in markers)
    ]
    return sorted(names)


def detect_vault_agents(vault):
    root = Path(vault)
    names = set()
    notes = root / "notes"
    if notes.is_dir():
        names.update(
            item.name for item in notes.iterdir() if item.is_dir() and item.name not in SKIP_LAYERS
        )
    for layer in (root / "projects").glob("*/notes"):
        if layer.is_dir():
            names.update(
                item.name
                for item in layer.iterdir()
                if item.is_dir() and item.name not in SKIP_LAYERS
            )
    return sorted(names)
