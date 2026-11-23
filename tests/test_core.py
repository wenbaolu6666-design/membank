import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from membank import (
    __version__,
    agents,
    check,
    i18n,
    indexer,
    mcp,
    signals,
    summary,
    templates,
)
from membank import config as cfg


class VaultDiscoveryTest(unittest.TestCase):
    def test_find_vault_walks_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes").mkdir()
            (root / "projects").mkdir()
            (root / "AGENTS.md").write_text("x", encoding="utf-8")
            nested = root / "projects" / "demo" / "notes"
            nested.mkdir(parents=True)
            self.assertEqual(cfg.find_vault(nested), root.resolve())

    def test_missing_vault_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(cfg.find_vault(tmp))


class FrontmatterTest(unittest.TestCase):
    def test_parse_and_body(self):
        text = "---\ntitle: 标题\nstatus: active\n---\n\n正文"
        data, body = indexer.parse_frontmatter(text)
        self.assertEqual(data["title"], "标题")
        self.assertIn("正文", body)

    def test_chunks_keep_title(self):
        chunks = indexer.make_chunks("标题", "第一段\n\n## 小节\n内容")
        self.assertTrue(all(chunk.startswith("标题") for chunk in chunks))
        self.assertGreaterEqual(len(chunks), 1)


class SignalTest(unittest.TestCase):
    def test_signal_id_is_order_independent(self):
        first = signals.signal_id("a.md", "b.md")
        second = signals.signal_id("b.md", "a.md")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)

    def test_lsh_keeps_identical_vectors(self):
        config = SimpleNamespace(
            signals_bruteforce_limit=0, signals_bands=4, signals_rows=4
        )
        items = [{"path": "a"}, {"path": "b"}]
        vectors = {"a": [1.0, 0.0, 0.0], "b": [1.0, 0.0, 0.0]}
        pairs = signals._candidate_pairs(items, vectors, config)
        self.assertTrue(pairs)


class SummaryTest(unittest.TestCase):
    def test_fit_respects_byte_limit(self):
        text = "v1\n\n## What's in Memory\n" + "\n".join(
            f"- 条目 {index}" for index in range(2000)
        )
        self.assertLessEqual(len(summary._fit(text).encode("utf-8")), summary.MAX_BYTES)


class TemplateTest(unittest.TestCase):
    def test_repo_files_match_embedded(self):
        root = Path(__file__).resolve().parent.parent / "templates" / "vault"
        if not root.is_dir():
            self.skipTest("repo templates not present")
        self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), templates.AGENTS_MD)
        self.assertEqual((root / "profile.md").read_text(encoding="utf-8"), templates.PROFILE_MD)


class CheckTest(unittest.TestCase):
    def _vault(self, root):
        (root / "notes").mkdir()
        (root / "projects" / "demo" / "notes" / "codex").mkdir(parents=True)
        (root / "AGENTS.md").write_text("x", encoding="utf-8")
        (root / "projects" / "demo" / "PROJECT.md").write_text(
            "---\npath: /tmp/demo\nslug: demo\n---\n", encoding="utf-8"
        )

    def test_detects_dangling_superseded_and_oneway_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._vault(root)
            base = root / "projects" / "demo" / "notes" / "codex"
            (base / "a.md").write_text(
                "---\ntitle: A\nscope: project\ntype: reference\nstatus: superseded\n"
                "agent: codex\nsupersededBy: notes/missing.md\nmirrors: [notes/b.md]\n---\nA\n",
                encoding="utf-8",
            )
            (base / "b.md").write_text(
                "---\ntitle: B\nscope: global\ntype: reference\nstatus: active\n---\nB\n",
                encoding="utf-8",
            )
            issues = check.collect(cfg.load_config(vault=root))
            codes = {issue["code"] for issue in issues}
            self.assertIn("superseded-target-missing", codes)
            self.assertIn("mirror-target-missing", codes)

    def test_valid_note_has_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._vault(root)
            note = root / "projects" / "demo" / "notes" / "codex" / "good.md"
            note.write_text(
                "---\ntitle: Good\nscope: project\ntype: reference\nstatus: active\nagent: codex\n---\nok\n",
                encoding="utf-8",
            )
            issues = check.collect(cfg.load_config(vault=root))
            errors = [item for item in issues if item["severity"] == "error"]
            self.assertEqual(errors, [])


class AgentsTest(unittest.TestCase):
    def test_detect_installed_from_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".codex").mkdir()
            (home / ".cursor").mkdir()
            self.assertEqual(agents.detect_installed(home), ["codex", "cursor"])

    def test_detect_vault_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes" / "codex").mkdir(parents=True)
            (root / "notes" / "archive").mkdir()
            (root / "projects" / "demo" / "notes" / "claude").mkdir(parents=True)
            self.assertEqual(agents.detect_vault_agents(root), ["claude", "codex"])


class SchemaSyncTest(unittest.TestCase):
    def test_enums_match_json_schema(self):
        path = Path(__file__).resolve().parent.parent / "schema" / "frontmatter.schema.json"
        if not path.is_file():
            self.skipTest("schema not present")
        schema = json.loads(path.read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(set(check.VALID_TYPES), set(properties["type"]["enum"]))
        self.assertEqual(set(check.VALID_SCOPES), set(properties["scope"]["enum"]))
        self.assertEqual(set(check.VALID_STATUSES), set(properties["status"]["enum"]))


class ConfigTest(unittest.TestCase):
    def test_state_dir_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes").mkdir()
            (root / "projects").mkdir()
            (root / "AGENTS.md").write_text("x", encoding="utf-8")
            (root / "memory-bank.toml").write_text('state_dir = ".state"\n', encoding="utf-8")
            config = cfg.load_config(vault=root)
            expected = (root / ".state").resolve()
            self.assertEqual(config.state_dir, expected)
            self.assertEqual(config.db.parent, expected)
            self.assertEqual(config.proposals.parent, expected)

    def test_git_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes").mkdir()
            (root / "projects").mkdir()
            (root / "AGENTS.md").write_text("x", encoding="utf-8")
            (root / "memory-bank.toml").write_text(
                '[git]\nmode = "cloud"\nremote = "https://example.com/x.git"\n',
                encoding="utf-8",
            )
            config = cfg.load_config(vault=root)
            self.assertTrue(config.git_enabled)
            self.assertEqual(config.git_mode, "cloud")
            self.assertEqual(config.git_remote, "https://example.com/x.git")


class VersionTest(unittest.TestCase):
    def test_version_consistency(self):
        root = Path(__file__).resolve().parent.parent
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["version"], __version__)
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(__version__, changelog)


class I18nTest(unittest.TestCase):
    def test_switch_language(self):
        try:
            i18n.set_lang("en")
            self.assertEqual(i18n.t("status.vault"), "vault")
            tools = mcp._handle({"method": "tools/list"}, None)["tools"]
            status = next(tool for tool in tools if tool["name"] == "memory_status")
            self.assertIn("vault path", status["description"])
        finally:
            i18n.set_lang("zh")
        self.assertEqual(i18n.t("status.vault"), "库根")


class SamplingTest(unittest.TestCase):
    def test_sampling_text_shapes(self):
        self.assertEqual(mcp._sampling_text({"content": {"text": "abc"}}), "abc")
        self.assertEqual(
            mcp._sampling_text({"content": [{"text": "a"}, {"text": "b"}]}), "ab"
        )
        self.assertEqual(mcp._sampling_text({}), "")


if __name__ == "__main__":
    unittest.main()
