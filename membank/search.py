"""Search committed Markdown chunks from the local SQLite retrieval database."""
import argparse
import math
import os
import sqlite3
import struct
import subprocess
import sys
from datetime import date

from .config import load_config
from .gitenv import clean_env
from .i18n import t

CONFIG = load_config()
BANK = str(CONFIG.vault)
DB_PATH = str(CONFIG.db)
DB_SCHEMA_VERSION = "2"
MAX_QUERY_CHARS = 1200


def normalized_path(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def is_ancestor(parent, child):
    try:
        return os.path.commonpath([parent, child]) == parent
    except ValueError:
        return False


def unpack_vector(blob):
    if not blob or len(blob) % 4:
        return []
    return struct.unpack("<" + "f" * (len(blob) // 4), blob)


def cosine(a, b):
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def project_ref_matches(project, slugs):
    if not project:
        return True
    value = str(project).replace("\\", "/").rstrip("/").split("/")[-1]
    return value.casefold() in slugs


def not_expired(valid_until):
    if not valid_until:
        return True
    try:
        return date.fromisoformat(str(valid_until)[:10]) >= date.today()
    except ValueError:
        return True


def visible_rows(rows, args, layer_chain, project_slugs):
    visible = []
    layer_rels = {layer["rel"] for layer in layer_chain}
    for row in rows:
        if row["status"] != "active":
            if not (args.include_temporary and row["status"] == "temporary"):
                continue
        if not not_expired(row["valid_until"]):
            continue
        if args.agent != "all" and row["agent"] not in (None, args.agent):
            continue

        layer_rel = row["layer_rel"] or ""
        if args.scope == "related":
            if layer_rel and layer_rel not in layer_rels:
                continue
            if not layer_rel and not project_ref_matches(row["project"], project_slugs):
                continue
        elif args.scope == "global":
            if row["scope"] != "global":
                continue
            if not project_ref_matches(row["project"], project_slugs):
                continue
        elif args.scope in {"project", "sub"}:
            if row["scope"] != args.scope or layer_rel not in layer_rels:
                continue
        visible.append(dict(row))
    return visible


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Search committed Markdown through its local SQLite mirror."
    )
    parser.add_argument("query", help="Natural-language search query")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--sem-weight", type=float, default=None)
    parser.add_argument("--path", default=os.getcwd(), help="Current project path")
    parser.add_argument(
        "--agent",
        choices=("shared", *CONFIG.agents, "all"),
        default="shared",
        help="Default is shared-only; choose your agent for shared + private notes",
    )
    parser.add_argument(
        "--scope",
        choices=("related", "global", "project", "sub", "all"),
        default="related",
    )
    parser.add_argument(
        "--include-temporary",
        action="store_true",
        help="Include non-expired temporary notes",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.top < 1:
        print("--top must be at least 1")
        return 2
    sem_weight = CONFIG.search_sem_weight if args.sem_weight is None else args.sem_weight
    if not 0.0 <= sem_weight <= 1.0:
        print("--sem-weight must be between 0 and 1")
        return 2
    if not os.path.exists(DB_PATH):
        print(t("search.no_db"))
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    meta = dict(conn.execute("SELECT key, value FROM metadata"))
    if meta.get("schema_version") != DB_SCHEMA_VERSION:
        conn.close()
        print(t("search.old_schema"))
        return 1
    layers = [
        dict(zip(("rel", "absolute_path", "slug", "parent", "depth"), row, strict=False))
        for row in conn.execute(
            "SELECT rel, absolute_path, slug, parent, depth FROM project_layers"
        )
    ]
    rows = conn.execute("SELECT * FROM documents").fetchall()

    target = normalized_path(args.path)
    layer_chain = [
        layer for layer in layers if is_ancestor(layer["absolute_path"], target)
    ]
    layer_chain.sort(key=lambda item: len(item["absolute_path"]))
    project_slugs = {layer["slug"].casefold() for layer in layer_chain}
    candidates = visible_rows(rows, args, layer_chain, project_slugs)
    if not candidates:
        conn.close()
        print(
            f"{t('search.no_candidates')} "
            f"(scope={args.scope}, agent={args.agent}, path={args.path})"
        )
        return 0

    by_path = {row["path"]: row for row in candidates}
    placeholders = ",".join("?" for _ in by_path)
    chunks = conn.execute(
        f"SELECT path, chunk_index, search_text, embedding FROM chunks "
        f"WHERE path IN ({placeholders}) ORDER BY path, chunk_index",
        tuple(by_path),
    ).fetchall()
    conn.close()
    if not chunks:
        print(t("search.no_chunks"))
        return 1

    from fastembed import TextEmbedding
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(CONFIG.search_ngram_min, CONFIG.search_ngram_max),
        max_features=CONFIG.search_max_features,
    )
    matrix = vectorizer.fit_transform(
        [row["search_text"][:MAX_QUERY_CHARS] for row in chunks] + [args.query]
    )
    keyword_scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    model = TextEmbedding(model_name=meta["model"])
    query_vector = list(model.embed([args.query[:MAX_QUERY_CHARS]]))[0]

    best_by_path = {}
    for index, chunk in enumerate(chunks):
        semantic_score = max(
            0.0, cosine(query_vector, unpack_vector(chunk["embedding"]))
        )
        keyword_score = float(keyword_scores[index])
        score = sem_weight * semantic_score + (1.0 - sem_weight) * keyword_score
        path = chunk["path"]
        result = (
            score,
            semantic_score,
            keyword_score,
            by_path[path],
            chunk["chunk_index"],
        )
        if path not in best_by_path or score > best_by_path[path][0]:
            best_by_path[path] = result

    results = sorted(best_by_path.values(), key=lambda item: item[0], reverse=True)
    current_head = subprocess.run(
        ["git", "-C", BANK, "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        env=clean_env(),
    ).stdout.decode("ascii", "replace").strip()
    chain = " -> ".join(layer["slug"] for layer in layer_chain) or "(global only)"
    print(
        t(
            "search.header",
            query=repr(args.query),
            count=len(candidates),
            chunks=len(chunks),
            chain=chain,
            agent=args.agent,
            model=meta["model"],
            commit=meta["source_commit"][:10],
        )
    )
    if CONFIG.git_enabled and current_head and current_head != meta.get("source_commit"):
        print(t("search.behind"))
    for score, semantic_score, keyword_score, row, chunk_index in results[: args.top]:
        print(
            f"  {score:.3f} (语{semantic_score:.2f}/词{keyword_score:.2f}) "
            f"#{chunk_index + 1} {row['path']} — {row['title']}"
        )
        print(f"    {row['absolute_path']}")

    try:
        from . import signals

        touched = {item[3]["path"] for item in results[: args.top]}
        hits = signals.visible(CONFIG, signals.detect(CONFIG, targets=touched))[:3]
        for item in hits:
            paths = " <-> ".join(item["paths"][:2])
            print(
                "  ! "
                + t("search.conflict", id=item["id"], kind=item["kind"], paths=paths)
            )
        if hits:
            print("    " + t("search.conflict_hint"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(t("search.fail", error=f"{type(exc).__name__}: {exc}"))
        sys.exit(1)
