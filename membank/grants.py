"""Time-limited read-only grants for cross-agent access."""
from __future__ import annotations

import json
import time
from datetime import datetime

GRANTS_FILE = "grants.json"
AUDIT_FILE = "audit.log"


def _grants_path(config):
    return config.state_dir / GRANTS_FILE


def load(config):
    path = _grants_path(config)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(config, data):
    path = _grants_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def grant(config, reader, target, minutes=30):
    if reader not in config.agents or target not in config.agents:
        raise RuntimeError("reader 与 target 都必须是已配置的智能体")
    if reader == target:
        raise RuntimeError("不需要给自己授权")
    data = load(config)
    data.setdefault(reader, {})[target] = int(time.time()) + max(1, minutes) * 60
    _save(config, data)
    return data[reader][target]


def revoke(config, reader, target=None):
    data = load(config)
    if reader not in data:
        return 0
    if target is None:
        removed = len(data[reader])
        data.pop(reader)
    else:
        removed = 1 if data[reader].pop(target, None) else 0
    _save(config, data)
    return removed


def allows(config, reader, target):
    if not reader or not target or reader == target:
        return False
    entry = load(config).get(reader, {}).get(target)
    return bool(entry and int(entry) > int(time.time()))


def active(config):
    now = int(time.time())
    rows = []
    for reader, targets in load(config).items():
        for target, expires in targets.items():
            if int(expires) > now:
                rows.append(
                    {
                        "reader": reader,
                        "target": target,
                        "expires_at": datetime.fromtimestamp(int(expires)).isoformat(
                            timespec="seconds"
                        ),
                    }
                )
    return rows


def audit(config, reader, target, action, path=""):
    entry = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "reader": reader,
        "target": target,
        "action": action,
        "path": path,
    }
    log = config.state_dir / AUDIT_FILE
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
