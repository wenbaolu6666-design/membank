"""Vault discovery and configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .agents import detect_vault_agents
from .i18n import detect_lang, set_lang, t

DEFAULT_STATE_DIR = ".membank"
VAULT_MARKERS = ("notes", "projects", "AGENTS.md")

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class Config:
    vault: Path
    state_dir: Path
    db: Path
    legacy_json: Path
    proposals: Path
    tasks: Path
    model: str
    agents: tuple
    chunk_chars: int = 900
    chunk_overlap: int = 120
    grant_minutes: int = 30
    conflict_similarity: float = 0.92
    title_similarity: float = 0.85
    signals_bands: int = 4
    signals_rows: int = 4
    signals_bruteforce_limit: int = 300
    signals_max_bucket: int = 800
    mcp_agent: str = ""
    lang: str = "zh"
    search_ngram_min: int = 2
    search_ngram_max: int = 4
    search_max_features: int = 50000
    search_sem_weight: float = 0.6
    ai_backend: str = "agent"
    ai_base_url: str = "http://127.0.0.1:11434/v1"
    ai_model: str = ""
    ai_key_env: str = "MEMBANK_AI_KEY"
    ai_allow_external: bool = False
    git_mode: str = "local"
    git_enabled: bool = True
    git_remote: str = ""
    git_auto_push: bool = False


def find_vault(start):
    """Return the nearest ancestor that looks like a memory vault."""
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in VAULT_MARKERS):
            return candidate
    return None


def read_toml(path):
    if not Path(path).is_file() or tomllib is None:
        return {}
    try:
        with open(path, "rb") as stream:
            return tomllib.load(stream)
    except (OSError, ValueError):
        return {}


def load_config(vault=None, start=None):
    """Resolve the vault root, database path and optional settings."""
    set_lang(detect_lang())
    explicit = vault or os.environ.get("MEMBANK_VAULT")
    root = Path(explicit).expanduser().resolve() if explicit else None
    if root is None:
        root = find_vault(start or Path.cwd()) or find_vault(
            Path(__file__).resolve().parent
        )
    if root is None:
        raise SystemExit(t("config.no_vault"))

    settings_path = Path(
        os.environ.get("MEMBANK_CONFIG") or root / "memory-bank.toml"
    )
    data = read_toml(settings_path)
    lang = str(
        os.environ.get("MEMBANK_LANG")
        or (data.get("i18n") or {}).get("lang")
        or detect_lang()
    )
    set_lang(lang)
    if data.get("vault"):
        root = Path(str(data["vault"])).expanduser().resolve()

    state_dir = Path(
        os.environ.get("MEMBANK_STATE_DIR") or data.get("state_dir") or DEFAULT_STATE_DIR
    )
    if not state_dir.is_absolute():
        state_dir = root / state_dir
    db = Path(os.environ.get("MEMBANK_DB") or data.get("db") or state_dir / "index.sqlite")
    if not db.is_absolute():
        db = root / db
    agents = data.get("agents")
    if not agents:
        env_agents = os.environ.get("MEMBANK_AGENTS", "")
        agents = [item.strip() for item in env_agents.split(",") if item.strip()]
    if not agents:
        agents = detect_vault_agents(root)
    conflicts = data.get("conflicts") or {}
    signals = data.get("signals") or {}
    security = data.get("security") or {}
    mcp = data.get("mcp") or {}
    search_config = data.get("search") or {}
    ai = data.get("ai") or {}
    git_config = data.get("git") or {}
    env_git = os.environ.get("MEMBANK_GIT")
    mode = str(git_config.get("mode") or "").strip().lower()
    remote = str(os.environ.get("MEMBANK_GIT_REMOTE") or git_config.get("remote") or "")
    if not mode:
        enabled = bool(git_config.get("enabled", True))
        mode = "cloud" if remote else ("local" if enabled else "none")
    if env_git:
        value = env_git.strip().lower()
        mode = {"0": "none", "false": "none", "no": "none", "off": "none"}.get(value, value)
    if mode not in {"local", "cloud"}:
        mode = "local"
    git_enabled = True
    return Config(
        vault=root,
        state_dir=state_dir,
        db=db,
        legacy_json=state_dir / "semantic-index.json",
        proposals=state_dir / "proposals",
        tasks=state_dir / "tasks",
        model=str(data.get("model") or ""),
        agents=tuple(str(agent) for agent in agents),
        chunk_chars=int(data.get("chunk_chars") or 900),
        chunk_overlap=int(data.get("chunk_overlap") or 120),
        grant_minutes=int(security.get("grant_minutes", 30)),
        conflict_similarity=float(conflicts.get("similarity", 0.92)),
        title_similarity=float(conflicts.get("title_similarity", 0.85)),
        signals_bands=int(signals.get("bands", 4)),
        signals_rows=int(signals.get("rows", 4)),
        signals_bruteforce_limit=int(signals.get("bruteforce_limit", 300)),
        signals_max_bucket=int(signals.get("max_bucket", 800)),
        mcp_agent=str(os.environ.get("MEMBANK_MCP_AGENT") or mcp.get("agent") or ""),
        lang=lang,
        search_ngram_min=int(search_config.get("ngram_min", 2)),
        search_ngram_max=int(search_config.get("ngram_max", 4)),
        search_max_features=int(search_config.get("max_features", 50000)),
        search_sem_weight=float(search_config.get("sem_weight", 0.6)),
        ai_backend=str(ai.get("backend") or "agent"),
        ai_base_url=str(ai.get("base_url") or "http://127.0.0.1:11434/v1"),
        ai_model=str(ai.get("model") or ""),
        ai_key_env=str(ai.get("api_key_env") or "MEMBANK_AI_KEY"),
        ai_allow_external=bool(ai.get("allow_external", False)),
        git_mode=mode,
        git_enabled=git_enabled,
        git_remote=remote,
        git_auto_push=bool(git_config.get("auto_push", False)),
    )
