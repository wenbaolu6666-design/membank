"""Structural validation for memory notes."""
from __future__ import annotations

import re
from datetime import date

import yaml

from .i18n import t

FRONTMATTER_RE = re.compile(r"^\ufeff?\s*---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
SKIP_DIRS = {
    ".git",
    ".obsidian",
    "archive",
    "conversations",
    "templates",
    "tests",
    "docs",
    "examples",
}
VALID_SCOPES = {"global", "project", "sub"}
VALID_TYPES = {"preference", "decision", "constraint", "lesson", "reference", "plan", "context"}
VALID_STATUSES = {"active", "temporary", "superseded", "archived"}
REQUIRED = ("title", "scope", "type", "status")
SPECIAL_FILES = {"AGENTS.md", "README.md", "profile.md", "index.md"}


def _issue(severity, code, path, **kwargs):
    key = "check." + code.replace("-", "_")
    return {"severity": severity, "code": code, "path": path, "message": t(key, **kwargs)}


def parse(text):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, text
    if not isinstance(data, dict):
        return None, text
    return data, text[match.end() :]


def iter_notes(config):
    skip = SKIP_DIRS | {config.state_dir.name}
    for path in config.vault.rglob("*.md"):
        relative = path.relative_to(config.vault).as_posix()
        parts = relative.split("/")
        if path.name in SPECIAL_FILES:
            continue
        if any(part in skip for part in parts[:-1]):
            continue
        if parts[0] == "notes":
            yield path, relative, parts
        elif parts[0] == "projects" and "notes" in parts:
            yield path, relative, parts


def _infer_agent(parts, agents):
    for index, part in enumerate(parts[:-1]):
        if part == "notes" and index + 1 < len(parts) - 1:
            candidate = parts[index + 1]
            if candidate in agents:
                return candidate
    return None


def _expected_scope(parts, agents):
    if parts[0] == "notes":
        return "global"
    try:
        notes_index = parts.index("notes")
    except ValueError:
        return None
    after = parts[notes_index + 1 : -1]
    if after and after[0] in agents:
        after = after[1:]
    return "sub" if after else "project"


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _resolve_target(target, by_relative):
    normalized = target.replace("\\\\", "/").lstrip("./")
    if normalized in by_relative:
        return normalized
    matches = [
        relative
        for relative in by_relative
        if relative == normalized or relative.endswith("/" + normalized)
    ]
    return matches[0] if len(matches) == 1 else None


def collect(config):
    notes = []
    by_relative = {}
    for path, relative, parts in iter_notes(config):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            notes.append((relative, parts, None, {}, {"read_error": str(exc)}))
            continue
        data, _body = parse(text)
        by_relative[relative] = {"path": path, "data": data or {}}
        notes.append((relative, parts, data, {}, {}))

    issues = []
    project_dirs = set()
    agents = set(config.agents)

    for relative, parts, data, _extra, errors in notes:
        if errors:
            issues.append(_issue("error", "unreadable", relative, error=errors["read_error"]))
            continue
        if data is None:
            issues.append(_issue("error", "frontmatter-missing", relative))
            continue

        for field in REQUIRED:
            if not data.get(field):
                issues.append(_issue("error", "field-missing", relative, field=field))

        scope = str(data.get("scope") or "")
        memory_type = str(data.get("type") or "")
        status = str(data.get("status") or "")
        if scope and scope not in VALID_SCOPES:
            issues.append(_issue("error", "scope-invalid", relative, scope=scope))
        if memory_type and memory_type not in VALID_TYPES:
            issues.append(_issue("error", "type-invalid", relative, type=memory_type))
        if status and status not in VALID_STATUSES:
            issues.append(_issue("error", "status-invalid", relative, status=status))

        expected_scope = _expected_scope(parts, agents)
        if scope and expected_scope and scope != expected_scope:
            issues.append(
                _issue("error", "scope-mismatch", relative, expected=expected_scope, scope=scope)
            )

        inferred_agent = _infer_agent(parts, agents)
        declared_agent = str(data.get("agent") or "").strip()
        if inferred_agent and declared_agent and declared_agent != inferred_agent:
            issues.append(
                _issue("warning", "agent-mismatch", relative, inferred=inferred_agent, declared=declared_agent)
            )
        if inferred_agent and not declared_agent:
            issues.append(_issue("warning", "agent-missing", relative, inferred=inferred_agent))

        superseded_by = str(data.get("supersededBy") or "").strip()
        if status == "superseded" and not superseded_by:
            issues.append(_issue("error", "superseded-missing", relative))
        if status == "superseded" and superseded_by:
            target = _resolve_target(superseded_by, by_relative)
            if target is None:
                issues.append(_issue("error", "superseded-target-missing", relative, target=superseded_by))
            else:
                target_status = str(by_relative[target]["data"].get("status") or "")
                if target_status == "superseded":
                    issues.append(_issue("warning", "superseded-chain", relative, target=target))
        if status and status != "superseded" and superseded_by:
            issues.append(_issue("warning", "superseded-stale", relative))

        valid_until = str(data.get("validUntil") or "")[:10]
        if status == "active" and valid_until and valid_until < date.today().isoformat():
            issues.append(_issue("warning", "expired", relative, date=valid_until))

        for mirror in _as_list(data.get("mirrors")):
            target = _resolve_target(mirror, by_relative)
            if target is None:
                issues.append(_issue("error", "mirror-target-missing", relative, target=mirror))
                continue
            back = _as_list(by_relative[target]["data"].get("mirrors"))
            normalized = {item.replace("\\\\", "/").lstrip("./") for item in back}
            if relative not in normalized:
                issues.append(_issue("warning", "mirror-oneway", relative, target=target))

        if parts[0] == "projects" and len(parts) > 1:
            project_dirs.add(parts[1])

    for slug in sorted(project_dirs):
        project_dir = config.vault / "projects" / slug
        if not (project_dir / "PROJECT.md").is_file():
            issues.append(_issue("error", "project-identity-missing", f"projects/{slug}"))

    return issues


def run(config, strict=False, verbose=False):
    issues = collect(config)
    errors = [item for item in issues if item["severity"] == "error"]
    warnings = [item for item in issues if item["severity"] == "warning"]
    if verbose:
        for item in errors + warnings:
            label = "ERROR" if item["severity"] == "error" else "WARN "
            print(f"{label} [{item['code']}] {item['path']}: {item['message']}")
    else:
        counts = {}
        for item in errors + warnings:
            counts[item["code"]] = counts.get(item["code"], 0) + 1
        for code, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True):
            print(f"{code:<30} {count}")
        if counts:
            print("\n" + t("check.verbose_hint"))
    print("\n" + t("check.summary", errors=len(errors), warnings=len(warnings)))
    if errors or (strict and warnings):
        return 1
    return 0
