"""Command line entry point for memory-bank."""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from .config import DEFAULT_STATE_DIR, load_config
from .gitenv import clean_env
from .i18n import detect_lang, set_lang, t
from .templates import AGENTS_MD, PROFILE_MD


def _configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_stdio()


USAGE = """membank <command>

  init <dir> [--agents a,b]   初始化一个记忆库
  index                       按 Git 模式同步检索索引
  search "查询" [选项]        检索记忆（--agent / --scope / --path）
  status                      查看索引与提交状态
  doctor                      检查依赖与环境
  mcp                         启动 MCP stdio 服务
  signals                     列出冲突信号
  dismiss <id>                忽略一条信号
  curate list                 列出待审提案
  curate show <id>            查看提案内容
  curate apply <id>           合入提案（可 --target / --overwrite）
  curate prepare [--since C]  生成整理任务，交给当前会话模型
  curate submit <file|->      提交当前会话模型的整理结果
  curate run                  按 backend 生成任务或调用 API
  summary build               生成派生摘要
  summary show                查看当前摘要
  inject                      输出可注入会话的记忆上下文
  check [--strict] [--verbose] 校验 frontmatter、分层与状态一致性
  migrate [--apply]           按 v2 规范迁移旧笔记
  supersede <旧...> --by <新> [--apply] 标记取代并回填链路
  grant <目标> [--to 读者] [--minutes N] 授权跨智能体只读（默认 30 分钟）
  grants                      查看有效授权
  revoke <目标> [--to 读者]    撤销授权
"""


def git_head(vault):
    result = subprocess.run(
        ["git", "-C", str(vault), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        env=clean_env(),
    )
    return result.stdout.decode("ascii", "replace").strip() if result.returncode == 0 else ""


def git_remote(vault):
    result = subprocess.run(
        ["git", "-C", str(vault), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
        env=clean_env(),
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _init_local_git(target):
    env = clean_env()
    probe = subprocess.run(["git", "--version"], capture_output=True, check=False, env=env)
    if probe.returncode != 0:
        print(t("init.git_missing"))
        return 1
    subprocess.run(
        ["git", "-C", str(target), "init"], capture_output=True, check=False, env=env
    )
    subprocess.run(
        ["git", "-C", str(target), "add", "-A"], capture_output=True, check=False, env=env
    )
    identity = False
    if not subprocess.run(
        ["git", "-C", str(target), "config", "user.name"],
        capture_output=True, text=True, env=env, check=False,
    ).stdout.strip():
        subprocess.run(
            ["git", "-C", str(target), "config", "user.name", "membank"],
            capture_output=True, check=False, env=env,
        )
        identity = True
    if not subprocess.run(
        ["git", "-C", str(target), "config", "user.email"],
        capture_output=True, text=True, env=env, check=False,
    ).stdout.strip():
        subprocess.run(
            ["git", "-C", str(target), "config", "user.email", "membank@localhost"],
            capture_output=True, check=False, env=env,
        )
        identity = True
    if identity:
        print(t("init.git_identity_default"))
    commit = subprocess.run(
        ["git", "-C", str(target), "commit", "-m", "init memory bank"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    output = (commit.stderr or "") + (commit.stdout or "")
    if commit.returncode != 0 and "nothing to commit" not in output:
        if "Please tell me who you are" in output or "unable to auto-detect email" in output:
            print(t("init.git_identity_missing"))
        else:
            print(t("init.git_failed", error=output.strip()))
        return 1
    print(t("init.git_done"))
    return 0


def cmd_index(argv):
    from . import indexer

    if argv:
        print(t("common.no_args", command="index"))
        return 2
    return indexer.main()


def cmd_search(argv):
    from . import search

    return search.main(argv)


def cmd_status(argv):
    if argv:
        print(t("common.no_args", command="status"))
        return 2
    config = load_config()
    print(f"{t('status.vault'):<6}: {config.vault}")
    print(f"{t('status.state'):<6}: {config.state_dir}")
    print(f"{t('status.index'):<6}: {config.db}")
    print(f"{t('status.model'):<6}: {config.model}")
    print(f"{t('status.agents'):<6}: {', '.join(config.agents)}")
    remote = git_remote(config.vault) or config.git_remote
    if config.git_mode == "none":
        vcs = t("status.vcs_none")
    elif config.git_mode == "cloud":
        vcs = t("status.vcs_remote", remote=remote or t("status.no_remote"))
    else:
        vcs = t("status.vcs_local")
    print(f"{t('status.vcs'):<6}: {vcs}")
    if not config.db.exists():
        print(f"{t('status.index'):<6}: {t('status.missing')}")
        return 1
    connection = sqlite3.connect(config.db)
    try:
        meta = dict(connection.execute("SELECT key, value FROM metadata"))
    except sqlite3.Error:
        print(f"{t('status.index'):<6}: {t('status.bad')}")
        return 1
    finally:
        connection.close()
    print(
        f"{t('status.index'):<6}: "
        + t(
            "status.stats",
            count=meta.get("count", "?"),
            chunks=meta.get("chunk_count", "?"),
            schema=meta.get("schema_version", "?"),
        )
    )
    head = git_head(config.vault)
    if head and meta.get("source_commit") != head:
        print(f"{t('status.index'):<6}: {t('status.behind')}")
    return 0


def cmd_doctor(argv):
    if argv:
        print(t("common.no_args", command="doctor"))
        return 2
    config = load_config()
    checks = [
        ("model", bool(config.model), config.model or t("doctor.model_missing")),
        ("vault", config.vault.is_dir(), str(config.vault)),
        (
            "git",
            (not config.git_enabled) or bool(git_head(config.vault)),
            t("status.vcs_none")
            if not config.git_enabled
            else (t("doctor.head_ok") if git_head(config.vault) else t("doctor.head_bad")),
        ),
    ]
    for module in ("yaml", "sklearn", "fastembed"):
        try:
            __import__(module)
            checks.append((module, True, t("doctor.installed")))
        except ImportError:
            checks.append((module, False, t("doctor.missing")))
    checks.append(("index", config.db.exists(), str(config.db)))
    failed = 0
    for name, ok, detail in checks:
        print(f"{'OK  ' if ok else 'FAIL'}  {name:<9} {detail}")
        failed += 0 if ok else 1
    return 0 if failed == 0 else 1


def cmd_init(argv):
    parser = argparse.ArgumentParser(prog="membank init")
    parser.add_argument("target")
    parser.add_argument("--agents", default=None)
    parser.add_argument("--state-dir", default=DEFAULT_STATE_DIR)
    parser.add_argument("--mode", choices=("none", "local", "cloud"), default="local")
    parser.add_argument("--remote", default="")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--git", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    mode = "local" if args.git else args.mode
    if args.remote and mode == "local":
        mode = "cloud"
    if mode == "cloud" and not args.remote:
        print(t("init.cloud_remote_required"))
        return 2
    target = Path(args.target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    for name in ("notes", "projects"):
        (target / name).mkdir(exist_ok=True)
        (target / name / ".gitkeep").touch(exist_ok=True)
    state_value = args.state_dir
    state_path = Path(state_value).expanduser()
    if not state_path.is_absolute():
        state_path = target / state_path
    state_path.mkdir(parents=True, exist_ok=True)
    from . import agents

    if args.agents:
        names = [item.strip() for item in args.agents.split(",") if item.strip()]
    else:
        names = agents.detect_installed() or agents.detect_vault_agents(target)

    for name, content in (("AGENTS.md", AGENTS_MD), ("profile.md", PROFILE_MD)):
        destination = target / name
        if destination.exists():
            continue
        destination.write_text(content, encoding="utf-8")
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        lines = [".obsidian/"]
        if not Path(state_value).is_absolute() and ".." not in Path(state_value).parts:
            lines.append(f"{state_value}/")
        lines.append("__pycache__/")
        gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config_file = target / "memory-bank.toml"
    if not config_file.exists():
        lines = []
        if names:
            lines.append(f"agents = {json.dumps(names, ensure_ascii=False)}")
        lines.append(f'state_dir = "{state_value}"')
        lines.append("")
        lines.append("[git]")
        lines.append(f'mode = "{mode}"')
        lines.append(f'remote = "{args.remote}"')
        lines.append(f"auto_push = {str(args.push).lower()}")
        config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(t("init.done", path=target))
    print(
        t("init.agents", agents=", ".join(names))
        if names
        else t("init.agents", agents=t("init.no_agents"))
    )
    print(t("init.state", path=state_path))
    if mode != "none":
        if _init_local_git(target) != 0:
            return 1
        if mode == "cloud" and args.remote:
            env = clean_env()
            subprocess.run(
                ["git", "-C", str(target), "remote", "add", "origin", args.remote],
                capture_output=True,
                check=False,
                env=env,
            )
            subprocess.run(
                ["git", "-C", str(target), "remote", "set-url", "origin", args.remote],
                capture_output=True,
                check=False,
                env=env,
            )
            print(t("init.git_remote", remote=args.remote))
            if args.push:
                pushed = subprocess.run(
                    ["git", "-C", str(target), "push", "-u", "origin", "main"],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )
                if pushed.returncode != 0:
                    print(
                        t(
                            "init.git_push_failed",
                            error=(pushed.stderr or pushed.stdout).strip(),
                        )
                    )
        print(t("init.next_git"))
    else:
        print(t("status.vcs_none"))
        print(t("init.next"))
    return 0


def cmd_mcp(argv):
    from . import mcp

    agent = None
    if argv:
        if len(argv) == 2 and argv[0] == "--agent":
            agent = argv[1]
        else:
            print(t("mcp.usage"))
            return 2
    return mcp.serve(agent)


def cmd_signals(argv):
    from . import signals

    if argv:
        print(t("common.no_args", command="signals"))
        return 2
    config = load_config()
    items = signals.visible(config, signals.detect(config))
    if not items:
        print(t("signals.none"))
        return 0
    for item in items:
        print(signals.format_signal(item))
    print("\n" + t("signals.summary", count=len(items)))
    return 0


def cmd_dismiss(argv):
    from . import signals

    reason = ""
    if "--reason" in argv:
        index = argv.index("--reason")
        if index + 1 >= len(argv):
            print(t("dismiss.usage"))
            return 2
        reason = argv[index + 1]
        argv = argv[:index] + argv[index + 2 :]
    if len(argv) != 1:
        print(t("dismiss.usage"))
        return 2
    config = load_config()
    if signals.dismiss(config, argv[0], reason):
        print(t("dismiss.done", id=argv[0]))
        return 0
    print(t("dismiss.notfound", id=argv[0]))
    return 1


def cmd_curate(argv):
    from . import curate

    if not argv:
        print(t("curate.usage"))
        return 2
    action, rest = argv[0], argv[1:]
    config = load_config()
    if action == "list":
        rows = curate.list_proposals(config)
        if not rows:
            print(t("curate.none"))
            return 0
        for row in rows:
            print(f"- {row['id']} | {row['status']} | {row['title']}")
        return 0
    if action == "show":
        if len(rest) != 1:
            print(t("curate.show_usage"))
            return 2
        print(curate.show_proposal(config, rest[0]))
        return 0
    if action == "apply":
        target = None
        overwrite = "--overwrite" in rest
        if "--target" in rest:
            index = rest.index("--target")
            if index + 1 >= len(rest):
                print(t("curate.apply_usage"))
                return 2
            target = rest[index + 1]
            rest = rest[:index] + rest[index + 2 :]
        rest = [item for item in rest if item != "--overwrite"]
        if len(rest) != 1:
            print(t("curate.apply_usage"))
            return 2
        destination = curate.apply_proposal(config, rest[0], target, overwrite)
        print(t("curate.applied", path=destination))
        print(t("curate.next"))
        return 0
    if action in ("prepare", "run"):
        from . import curate_flow

        since = None
        limit = 20
        index = 0
        while index < len(rest):
            if rest[index] == "--since" and index + 1 < len(rest):
                since = rest[index + 1]
                index += 2
                continue
            if rest[index] == "--limit" and index + 1 < len(rest):
                limit = int(rest[index + 1])
                index += 2
                continue
            print(t("curate.unknown_arg", arg=rest[index]))
            return 2
        task, path = curate_flow.prepare(config, since, limit)
        if action == "run" and config.ai_backend == "api":
            created = curate_flow.run_api(config, task)
            print(t("curate.api_created", count=len(created)))
            return 0
        print(t("curate.task", path=path))
        print(task["instructions"])
        print("完成后：membank curate submit <结果.json>")
        return 0
    if action == "submit":
        from . import curate_flow

        if len(rest) != 1:
            print(t("curate.submit_usage"))
            return 2
        raw = sys.stdin.read() if rest[0] == "-" else Path(rest[0]).read_text(encoding="utf-8")
        created = curate_flow.submit(config, json.loads(raw))
        print(t("curate.created", count=len(created)))
        for identifier in created:
            print(f"- {identifier}")
        return 0
    print(t("curate.unknown", action=action))
    return 2


def cmd_summary(argv):
    from . import summary

    action = argv[0] if argv else "show"
    config = load_config()
    if action == "build":
        path, text = summary.build(config)
        print(t("summary.built", path=path, bytes=len(text.encode("utf-8"))))
        return 0
    if action == "show":
        print(summary.load(config))
        return 0
    print(t("summary.usage"))
    return 2


def cmd_inject(argv):
    from . import summary

    if argv:
        print(t("common.no_args", command="inject"))
        return 2
    print(summary.context_block(load_config()))
    return 0


def cmd_check(argv):
    from . import check

    strict = "--strict" in argv
    verbose = "--verbose" in argv
    unknown = [item for item in argv if item not in ("--strict", "--verbose")]
    if unknown:
        print(t("check.usage"))
        return 2
    return check.run(load_config(), strict, verbose)


def cmd_migrate(argv):
    from . import migrate

    apply = "--apply" in argv
    unknown = [item for item in argv if item != "--apply"]
    if unknown:
        print("用法：membank migrate [--apply]")
        return 2
    config = load_config()
    changes = migrate.plan(config)
    counts = {}
    for change in changes:
        for reason in change["reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    for reason, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True):
        print(f"{reason:<12} {count}")
    print(f"\n共 {len(changes)} 个文件需要调整")
    for change in changes[:10]:
        print(f"- {change['relative']} [{', '.join(change['reasons'])}]")
    if not apply:
        print("\n这是 dry-run；加 --apply 才会写文件")
        return 0
    written, _ = migrate.apply(config)
    print(f"已写入 {written} 个文件")
    return 0


def cmd_supersede(argv):
    from . import supersede

    if "--by" not in argv:
        print("用法：membank supersede <旧笔记...> --by <新笔记> [--apply]")
        return 2
    index = argv.index("--by")
    if index + 1 >= len(argv):
        print("用法：membank supersede <旧笔记...> --by <新笔记> [--apply]")
        return 2
    new = argv[index + 1]
    apply = "--apply" in argv
    olds = [item for item in argv[:index] if item != "--apply"]
    if not olds:
        print("至少指定一条旧笔记")
        return 2
    config = load_config()
    changes = supersede.plan(config, olds, new)
    for relative, entry in changes.items():
        print(f"- {relative} [{', '.join(entry['reasons'])}]")
    if not apply:
        print("\n这是 dry-run；加 --apply 才会写文件")
        return 0
    supersede.apply(config, olds, new)
    print(f"已写入 {len(changes)} 个文件")
    return 0


def cmd_grant(argv):
    from . import grants

    if not argv:
        print(t("grant.usage"))
        return 2
    config = load_config()
    target = argv[0]
    reader = config.mcp_agent
    minutes = config.grant_minutes
    rest = argv[1:]
    for index, item in enumerate(rest):
        if item == "--to" and index + 1 < len(rest):
            reader = rest[index + 1]
        if item == "--minutes" and index + 1 < len(rest):
            minutes = int(rest[index + 1])
    if not reader:
        print(t("grant.need_reader"))
        return 2
    grants.grant(config, reader, target, minutes)
    print(t("grant.done", reader=reader, target=target, minutes=minutes))
    return 0


def cmd_grants(argv):
    from . import grants

    config = load_config()
    rows = grants.active(config)
    if not rows:
        print(t("grants.none"))
        return 0
    for row in rows:
        print(t("grants.line", reader=row["reader"], target=row["target"], expires=row["expires_at"]))
    return 0


def cmd_revoke(argv):
    from . import grants

    if not argv:
        print(t("revoke.usage"))
        return 2
    config = load_config()
    target = argv[0]
    reader = config.mcp_agent
    if "--to" in argv:
        index = argv.index("--to")
        if index + 1 < len(argv):
            reader = argv[index + 1]
    if not reader:
        print(t("grant.need_reader"))
        return 2
    removed = grants.revoke(config, reader, target)
    print(t("revoke.done", count=removed))
    return 0


COMMANDS = {
    "init": cmd_init,
    "index": cmd_index,
    "search": cmd_search,
    "status": cmd_status,
    "doctor": cmd_doctor,
    "mcp": cmd_mcp,
    "signals": cmd_signals,
    "dismiss": cmd_dismiss,
    "curate": cmd_curate,
    "summary": cmd_summary,
    "inject": cmd_inject,
    "check": cmd_check,
    "migrate": cmd_migrate,
    "supersede": cmd_supersede,
    "grant": cmd_grant,
    "grants": cmd_grants,
    "revoke": cmd_revoke,
}


def main(argv=None):
    _configure_stdio()
    set_lang(detect_lang())
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(t("usage"))
        return 0
    command, rest = args[0], args[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"未知命令：{command}\n")
        print(t("usage"))
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
