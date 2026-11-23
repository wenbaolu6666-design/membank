"""Mirror committed Markdown notes into the local SQLite retrieval database."""
import hashlib
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import PurePosixPath

from .config import load_config
from .i18n import t

try:
    CONFIG = load_config()
except SystemExit:
    CONFIG = None
BANK = str(CONFIG.vault) if CONFIG else ""
DB_PATH = str(CONFIG.db) if CONFIG else ""
LEGACY_JSON_PATH = str(CONFIG.legacy_json) if CONFIG else ""
SKIP_DIRS = {
    ".git",
    ".obsidian",
    "archive",
    "conversations",
    "tools",
    "docs",
    "templates",
    "tests",
    "examples",
}
if CONFIG:
    SKIP_DIRS.add(CONFIG.state_dir.name)
SKIP_FILES = {"index.md", ".gitkeep"}
AGENTS = set(CONFIG.agents) if CONFIG else set()
CHUNK_CHARS = CONFIG.chunk_chars if CONFIG else 900
CHUNK_OVERLAP = CONFIG.chunk_overlap if CONFIG else 120
DB_SCHEMA_VERSION = "2"
VALID_SCOPES = {"global", "project", "sub"}
VALID_STATUSES = {"active", "temporary", "superseded", "archived"}


def git(*args):
    return subprocess.run(
        ["git", "-C", BANK, *args],
        capture_output=True,
        check=False,
    )


def read_committed_sources():
    tree = git("ls-tree", "-r", "--name-only", "-z", "HEAD")
    if tree.returncode:
        raise RuntimeError(tree.stderr.decode("utf-8", "replace").strip())
    changed = git("diff", "HEAD", "--name-only", "-z")
    if changed.returncode:
        raise RuntimeError(changed.stderr.decode("utf-8", "replace").strip())
    changed_paths = {
        path.decode("utf-8", "replace").replace("\\", "/")
        for path in changed.stdout.split(b"\0")
        if path
    }

    sources = {}
    for raw in tree.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "replace").replace("\\", "/")
        parts = PurePosixPath(rel).parts
        if not rel.lower().endswith(".md") or PurePosixPath(rel).name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS or part.startswith(".") for part in parts[:-1]):
            continue

        if rel in changed_paths:
            result = git("show", f"HEAD:{rel}")
            if result.returncode:
                continue
            text = result.stdout.decode("utf-8", "replace")
        else:
            path = os.path.join(BANK, *rel.split("/"))
            try:
                with open(path, encoding="utf-8") as stream:
                    text = stream.read()
            except OSError:
                result = git("show", f"HEAD:{rel}")
                if result.returncode:
                    continue
                text = result.stdout.decode("utf-8", "replace")
        sources[rel] = text
    return sources


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            try:
                import yaml

                data = yaml.safe_load("\n".join(lines[1:end])) or {}
                if not isinstance(data, dict):
                    return {}, text
                return data, "\n".join(lines[end + 1 :])
            except Exception:
                return {}, text
    return {}, text


def as_text(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def make_chunks(title, body):
    limit = max(100, CHUNK_CHARS - len(title) - 1)
    sections = re.split(r"(?m)(?=^#{1,6}\s+)", body)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= limit:
            chunks.append(title + "\n" + section)
            continue

        offset = 0
        while offset < len(section):
            end = min(offset + limit, len(section))
            if end < len(section):
                boundary = section.rfind("\n", offset, end)
                if boundary > offset + limit // 2:
                    end = boundary
            excerpt = section[offset:end].strip()
            if excerpt:
                chunks.append(title + "\n" + excerpt)
            if end >= len(section):
                break
            offset = max(offset + 1, end - CHUNK_OVERLAP)
    return chunks or [title + "\n" + body[:limit]]


def read_source_files(sources):
    files = []
    for rel, text in sorted(sources.items()):
        if len(text.strip()) < 30:
            continue
        frontmatter, body = parse_frontmatter(text)
        fallback = os.path.splitext(PurePosixPath(rel).name)[0]
        title = as_text(frontmatter.get("title")) or fallback
        if rel.startswith("projects/") and PurePosixPath(rel).name == "PROJECT.md":
            continue
        files.append(
            {
                "path": rel,
                "text": text,
                "frontmatter": frontmatter,
                "title": title,
                "chunks": make_chunks(title, body),
                "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return files


def read_project_layers(sources):
    layers = []
    for rel, text in sources.items():
        if not rel.startswith("projects/") or PurePosixPath(rel).name != "PROJECT.md":
            continue
        data, _ = parse_frontmatter(text)
        absolute_path = as_text(data.get("path"))
        if not absolute_path:
            continue
        rel_dir = PurePosixPath(rel).parent.as_posix()
        layers.append(
            {
                "rel": rel_dir,
                "absolute_path": os.path.normcase(
                    os.path.normpath(os.path.abspath(absolute_path))
                ),
                "slug": as_text(data.get("slug")) or PurePosixPath(rel_dir).name,
                "parent": as_text(data.get("parent")),
                "depth": len(PurePosixPath(rel_dir).parts) - 1,
            }
        )
    return sorted(layers, key=lambda item: len(item["rel"]), reverse=True)


def classify_document(doc, layers):
    rel = doc["path"]
    fm = doc["frontmatter"]
    layer = next(
        (
            item
            for item in layers
            if rel == item["rel"] + "/PROJECT.md"
            or rel.startswith(item["rel"] + "/")
        ),
        None,
    )
    scope = (
        ("project" if layer["depth"] == 1 else "sub")
        if layer
        else as_text(fm.get("scope"))
    )
    if scope not in VALID_SCOPES:
        scope = "global"

    parts = PurePosixPath(rel).parts
    inferred_agent = None
    for index, part in enumerate(parts[:-1]):
        if part == "notes" and parts[index + 1] in AGENTS:
            inferred_agent = parts[index + 1]
            break
    metadata = fm.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    declared_agent = as_text(fm.get("agent") or metadata.get("agent"))
    agent = inferred_agent or (declared_agent or None)

    status = (as_text(fm.get("status")) or "active").strip().lower()
    if status not in VALID_STATUSES:
        status = "active"
    mirrors = fm.get("mirrors", [])
    if not isinstance(mirrors, list):
        mirrors = [mirrors]
    return {
        **doc,
        "absolute_path": os.path.join(BANK, *rel.split("/")),
        "scope": scope,
        "agent": agent,
        "project": as_text(fm.get("project")) or (layer["slug"] if layer else None),
        "layer_rel": layer["rel"] if layer else "",
        "status": status,
        "valid_until": as_text(fm.get("validUntil")),
        "memory_type": as_text(fm.get("type")),
        "source": as_text(fm.get("source")),
        "confidence": as_text(fm.get("confidence")),
        "mirrors": json.dumps(mirrors, ensure_ascii=False),
    }


def read_previous_index():
    if not os.path.exists(DB_PATH):
        return None, {}
    try:
        conn = sqlite3.connect(DB_PATH)
        meta = dict(conn.execute("SELECT key, value FROM metadata"))
        if meta.get("schema_version") != DB_SCHEMA_VERSION:
            conn.close()
            return None, {}
        doc_rows = conn.execute(
            "SELECT path, source_hash FROM documents"
        ).fetchall()
        chunk_rows = conn.execute(
            "SELECT path, chunk_index, search_text, embedding FROM chunks "
            "ORDER BY path, chunk_index"
        ).fetchall()
        conn.close()
        chunks = {}
        for path, chunk_index, search_text, embedding in chunk_rows:
            chunks.setdefault(path, []).append(
                {"index": chunk_index, "text": search_text, "embedding": embedding}
            )
        previous = {
            path: {"source_hash": source_hash, "chunks": chunks.get(path, [])}
            for path, source_hash in doc_rows
        }
        return meta, previous
    except sqlite3.Error:
        return None, {}


def choose_model(previous_meta):
    if CONFIG is None or not CONFIG.model:
        raise RuntimeError(t("index.no_model"))
    return CONFIG.model


def pack_vector(vector):
    values = [float(value) for value in vector]
    return struct.pack("<" + "f" * len(values), *values), values


def write_json_atomic(payload):
    target_dir = os.path.dirname(LEGACY_JSON_PATH)
    os.makedirs(target_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=".semantic-index-", suffix=".tmp", dir=target_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        os.replace(temp_path, LEGACY_JSON_PATH)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def main():
    global CONFIG, BANK, DB_PATH, LEGACY_JSON_PATH, AGENTS, CHUNK_CHARS, CHUNK_OVERLAP
    if CONFIG is None:
        CONFIG = load_config()
        BANK = str(CONFIG.vault)
        DB_PATH = str(CONFIG.db)
        LEGACY_JSON_PATH = str(CONFIG.legacy_json)
        AGENTS = set(CONFIG.agents)
        CHUNK_CHARS = CONFIG.chunk_chars
        CHUNK_OVERLAP = CONFIG.chunk_overlap
        SKIP_DIRS.add(CONFIG.state_dir.name)
    try:
        import yaml  # noqa: F401
        from fastembed import TextEmbedding
    except ImportError as exc:
        print(t("index.missing_deps", error=exc))
        return 1

    source_head = git("rev-parse", "HEAD").stdout.decode("ascii", "replace").strip()
    sources = read_committed_sources()
    files = read_source_files(sources)
    layers = read_project_layers(sources)
    if not files:
        print(t("index.no_notes"))
        return 1

    previous_meta, previous_documents = read_previous_index()
    model_name = choose_model(previous_meta)
    model = TextEmbedding(model_name=model_name)
    model_name = getattr(model, "model_name", model_name)

    docs = [classify_document(doc, layers) for doc in files]
    pending_chunks = []
    reused_chunks = 0
    chunk_count = sum(len(doc["chunks"]) for doc in docs)
    for doc in docs:
        old = previous_documents.get(doc["path"])
        if (
            old
            and previous_meta
            and previous_meta.get("model") == model_name
            and old["source_hash"] == doc["source_hash"]
            and [chunk["text"] for chunk in old["chunks"]] == doc["chunks"]
        ):
            doc["indexed_chunks"] = old["chunks"]
            reused_chunks += len(old["chunks"])
        else:
            doc["indexed_chunks"] = [
                {"index": index, "text": text, "embedding": None}
                for index, text in enumerate(doc["chunks"])
            ]
            pending_chunks.extend((doc, chunk) for chunk in doc["indexed_chunks"])

    embedded = (
        list(model.embed([chunk["text"] for _, chunk in pending_chunks]))
        if pending_chunks
        else []
    )
    for (_, chunk), vector in zip(pending_chunks, embedded, strict=False):
        chunk["embedding"], _ = pack_vector(vector)

    json_docs = []
    for doc in docs:
        blob = doc["indexed_chunks"][0]["embedding"]
        values = struct.unpack("<" + "f" * (len(blob) // 4), blob)
        json_docs.append(
            {
                "path": doc["path"],
                "title": doc["title"],
                "emb": [round(value, 5) for value in values],
            }
        )

    built = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    fd, temp_db = tempfile.mkstemp(
        prefix=".memory-index-", suffix=".sqlite", dir=os.path.dirname(DB_PATH)
    )
    os.close(fd)
    conn = None
    try:
        conn = sqlite3.connect(temp_db)
        conn.executescript(
            """
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE project_layers (
                rel TEXT PRIMARY KEY,
                absolute_path TEXT NOT NULL,
                slug TEXT NOT NULL,
                parent TEXT,
                depth INTEGER NOT NULL
            );
            CREATE TABLE documents (
                path TEXT PRIMARY KEY,
                absolute_path TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                scope TEXT NOT NULL,
                agent TEXT,
                project TEXT,
                layer_rel TEXT NOT NULL,
                status TEXT NOT NULL,
                valid_until TEXT,
                memory_type TEXT,
                source TEXT,
                confidence TEXT,
                mirrors TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL
            );
            CREATE TABLE chunks (
                path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                search_text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                PRIMARY KEY(path, chunk_index)
            );
            CREATE INDEX documents_scope_agent_status
                ON documents(scope, agent, status);
            CREATE INDEX documents_layer ON documents(layer_rel);
            CREATE INDEX chunks_path ON chunks(path);
            """
        )
        metadata = {
            "schema_version": DB_SCHEMA_VERSION,
            "model": model_name,
            "dimension": str(
                len(docs[0]["indexed_chunks"][0]["embedding"]) // 4
            ),
            "built": built,
            "source_commit": source_head,
            "count": str(len(docs)),
            "chunk_count": str(chunk_count),
        }
        conn.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items()
        )
        conn.executemany(
            """INSERT INTO project_layers(rel, absolute_path, slug, parent, depth)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    layer["rel"],
                    layer["absolute_path"],
                    layer["slug"],
                    layer["parent"],
                    layer["depth"],
                )
                for layer in layers
            ],
        )
        conn.executemany(
            """INSERT INTO documents(
                   path, absolute_path, title, content, scope, agent, project,
                   layer_rel, status, valid_until, memory_type, source, confidence,
                   mirrors, source_hash, chunk_count
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    doc["path"],
                    doc["absolute_path"],
                    doc["title"],
                    doc["text"],
                    doc["scope"],
                    doc["agent"],
                    doc["project"],
                    doc["layer_rel"],
                    doc["status"],
                    doc["valid_until"],
                    doc["memory_type"],
                    doc["source"],
                    doc["confidence"],
                    doc["mirrors"],
                    doc["source_hash"],
                    len(doc["indexed_chunks"]),
                )
                for doc in docs
            ],
        )
        conn.executemany(
            """INSERT INTO chunks(path, chunk_index, search_text, embedding)
               VALUES (?, ?, ?, ?)""",
            [
                (doc["path"], chunk["index"], chunk["text"], chunk["embedding"])
                for doc in docs
                for chunk in doc["indexed_chunks"]
            ],
        )
        conn.commit()
        conn.close()
        conn = None
        os.replace(temp_db, DB_PATH)
    except Exception:
        if conn is not None:
            conn.close()
        if os.path.exists(temp_db):
            os.remove(temp_db)
        raise

    try:
        write_json_atomic(
            {
                "model": model_name,
                "dim": len(docs[0]["indexed_chunks"][0]["embedding"]) // 4,
                "built": built,
                "count": len(docs),
                "docs": json_docs,
            }
        )
    except OSError as exc:
        print(t("index.json_warn", error=exc))

    print(
        t(
            "index.sync",
            docs=len(docs),
            chunks=chunk_count,
            new=len(pending_chunks),
            reused=reused_chunks,
            layers=len(layers),
            model=model_name,
        )
    )
    print(f"SQLite: {DB_PATH}")
    try:
        from . import check

        errors = [item for item in check.collect(CONFIG) if item["severity"] == "error"]
        if errors:
            print(t("index.hint", errors=len(errors)))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(t("index.fail", error=f"{type(exc).__name__}: {exc}"))
        sys.exit(1)
