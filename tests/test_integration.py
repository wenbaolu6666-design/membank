import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from membank import check, cli, curate, grants, mcp, notes, supersede
from membank import config as cfg

ROOT = Path(__file__).resolve().parent.parent


def make_vault(root):
    (root / "notes").mkdir()
    (root / "projects").mkdir()
    (root / "AGENTS.md").write_text("x", encoding="utf-8")


class CurateIntegrationTest(unittest.TestCase):
    def test_propose_then_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            config = cfg.load_config(vault=root)
            mcp._tool_propose(
                config,
                {"title": "集成测试提案", "content": "正文", "scope": "global", "agent": "codex"},
            )
            rows = curate.list_proposals(config)
            self.assertEqual(len(rows), 1)
            destination = curate.apply_proposal(config, rows[0]["id"])
            self.assertTrue(destination.is_file())
            self.assertIn("status: active", destination.read_text(encoding="utf-8"))


class InitIntegrationTest(unittest.TestCase):
    def test_init_writes_detected_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.assertEqual(
                cli.cmd_init(
                    [str(root), "--agents", "codex,claude", "--state-dir", ".state"]
                ),
                0,
            )
            self.assertTrue((root / "AGENTS.md").is_file())
            self.assertTrue((root / ".state").is_dir())
            config_text = (root / "memory-bank.toml").read_text(encoding="utf-8")
            self.assertIn("codex", config_text)
            self.assertIn("claude", config_text)
            self.assertIn('state_dir = ".state"', config_text)
            gitignore = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".state/", gitignore)


class CurateFlowTest(unittest.TestCase):
    def test_prepare_and_submit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            database = root / ".membank" / "index.sqlite"
            database.parent.mkdir()
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE documents(path, title, scope, agent, memory_type, "
                "layer_rel, content, status)"
            )
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("notes/codex/a.md", "A", "global", "codex", "reference", "", "body", "active"),
            )
            connection.commit()
            connection.close()
            config = cfg.load_config(vault=root)
            config.agents = ("codex", "zcode")
            config.mcp_agent = "codex"
            from membank import curate_flow

            task, path = curate_flow.prepare(config, limit=5)
            self.assertTrue(path.is_file())
            self.assertTrue(task["changed"])
            created = curate_flow.submit(
                config,
                {
                    "task_id": task["task_id"],
                    "proposals": [
                        {
                            "title": "整理结果",
                            "content": "内容",
                            "scope": "global",
                            "type": "reference",
                            "agent": "codex",
                        }
                    ],
                },
            )
            self.assertEqual(len(created), 1)
            self.assertEqual(len(curate.list_proposals(config)), 1)


class AddNoteTest(unittest.TestCase):
    def test_confirmed_write_only_to_own_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            config = cfg.load_config(vault=root)
            config.agents = ("codex", "zcode")
            config.mcp_agent = "codex"
            with self.assertRaises(RuntimeError):
                notes.add_note(config, "未确认", "内容")
            target = notes.add_note(
                config, "已确认", "内容", scope="global", confirmed=True
            )
            self.assertEqual(target.parent, root / "notes" / "codex")
            text = target.read_text(encoding="utf-8")
            self.assertIn("status: active", text)
            self.assertIn("agent: codex", text)
            self.assertTrue((root / ".membank" / "audit.log").is_file())
            with self.assertRaises(RuntimeError):
                notes.add_note(config, "已确认", "重复", scope="global", confirmed=True)

    def test_project_scope_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            (root / "projects" / "demo").mkdir()
            config = cfg.load_config(vault=root)
            config.agents = ("codex",)
            config.mcp_agent = "codex"
            target = notes.add_note(
                config, "项目笔记", "内容", scope="project", project="demo", confirmed=True
            )
            self.assertEqual(
                target.parent, root / "projects" / "demo" / "notes" / "codex"
            )


class SupersedeTest(unittest.TestCase):
    def test_repoints_existing_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            (root / "notes" / "a.md").write_text(
                "---\ntitle: A\nscope: global\ntype: reference\nstatus: superseded\n"
                "supersededBy: notes/b.md\n---\na\n",
                encoding="utf-8",
            )
            (root / "notes" / "b.md").write_text(
                "---\ntitle: B\nscope: global\ntype: reference\nstatus: active\n---\nb\n",
                encoding="utf-8",
            )
            (root / "notes" / "c.md").write_text(
                "---\ntitle: C\nscope: global\ntype: reference\nstatus: active\n---\nc\n",
                encoding="utf-8",
            )
            config = cfg.load_config(vault=root)
            changes = supersede.plan(config, ["notes/b.md"], "notes/c.md")
            self.assertIn("repoint", changes["notes/a.md"]["reasons"])
            supersede.apply(config, ["notes/b.md"], "notes/c.md")
            data, _ = check.parse((root / "notes" / "a.md").read_text(encoding="utf-8"))
            self.assertEqual(data["supersededBy"], "notes/c.md")
            data, _ = check.parse((root / "notes" / "b.md").read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "superseded")


class McpHandshakeTest(unittest.TestCase):
    def test_protocol_negotiation_and_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            payload = "\n".join(
                [
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {"protocolVersion": "2024-11-05"},
                        }
                    ),
                    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                ]
            ) + "\n"
            env = dict(os.environ, MEMBANK_VAULT=str(root))
            result = subprocess.run(
                [sys.executable, "-m", "membank", "mcp"],
                input=payload,
                text=True,
                capture_output=True,
                cwd=ROOT,
                env=env,
                check=False,
            )
            lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            self.assertEqual(lines[0]["result"]["protocolVersion"], "2024-11-05")
            names = {tool["name"] for tool in lines[1]["result"]["tools"]}
            self.assertIn("memory_search", names)
            self.assertIn("memory_summary", names)


class McpIsolationTest(unittest.TestCase):
    def test_private_layers_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vault(root)
            (root / "notes" / "codex").mkdir(parents=True)
            (root / "notes" / "zcode").mkdir(parents=True)
            (root / "notes" / "codex" / "a.md").write_text(
                "---\ntitle: A\nscope: global\ntype: reference\nstatus: active\nagent: codex\n---\na\n",
                encoding="utf-8",
            )
            (root / "notes" / "zcode" / "b.md").write_text(
                "---\ntitle: B\nscope: global\ntype: reference\nstatus: active\nagent: zcode\n---\nb\n",
                encoding="utf-8",
            )
            (root / "notes" / "shared.md").write_text(
                "---\ntitle: S\nscope: global\ntype: reference\nstatus: active\n---\ns\n",
                encoding="utf-8",
            )
            config = cfg.load_config(vault=root)
            config.mcp_agent = "codex"
            database = root / ".membank" / "index.sqlite"
            database.parent.mkdir()
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE documents(path, title, scope, agent, status, layer_rel)"
            )
            connection.executemany(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("notes/codex/a.md", "A", "global", "codex", "active", ""),
                    ("notes/zcode/b.md", "B", "global", "zcode", "active", ""),
                    ("notes/shared.md", "S", "global", None, "active", ""),
                ],
            )
            connection.commit()
            connection.close()

            listing = mcp._tool_list(config, {"limit": 10})
            self.assertIn("notes/codex/a.md", listing)
            self.assertIn("notes/shared.md", listing)
            self.assertNotIn("notes/zcode/b.md", listing)
            self.assertIn("s", mcp._tool_read(config, {"path": "notes/shared.md"}))
            with self.assertRaises(RuntimeError):
                mcp._tool_read(config, {"path": "notes/zcode/b.md"})
            with self.assertRaises(RuntimeError):
                mcp._resolve_target(config, "zcode")
            grants.grant(config, "codex", "zcode", 30)
            self.assertIn(
                "b",
                mcp._tool_read(config, {"path": "notes/zcode/b.md", "agent": "zcode"}),
            )
            cross_listing = mcp._tool_list(config, {"agent": "zcode", "limit": 10})
            self.assertIn("notes/zcode/b.md", cross_listing)
            self.assertNotIn("notes/codex/a.md", cross_listing)
            self.assertTrue((root / ".membank" / "audit.log").is_file())
            grants.revoke(config, "codex", "zcode")
            with self.assertRaises(RuntimeError):
                mcp._tool_read(config, {"path": "notes/zcode/b.md", "agent": "zcode"})
            with self.assertRaises(RuntimeError):
                mcp._tool_propose(
                    config, {"title": "x", "content": "y", "agent": "zcode"}
                )


if __name__ == "__main__":
    unittest.main()
