"""Verify Codex hook lifecycle, pane isolation, and passive hook output."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "tmux/codex-monitor.py"
SPEC = importlib.util.spec_from_file_location("codex_monitor", MODULE)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


class CodexMonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {
            "XDG_STATE_HOME": self.directory.name,
            "TMUX": "/tmp/isolated-codex-test,123,0", "TMUX_PANE": "%1",
            "CODEX_TMUX_MONITOR": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.published = []

        def tmux(socket, *args):
            if args[0] == "display-message":
                return "@1"
            if args[0] == "list-panes":
                return "%1\n%2"
            self.published.append((socket, args))
            return ""

        self.tmux = patch.object(monitor, "tmux", side_effect=tmux)
        self.tmux.start()
        self.addCleanup(self.tmux.stop)

    def hook(self, name, session="root", **fields):
        monitor.handle_hook(dict(session_id=session, hook_event_name=name,
                                 cwd="/project with # spaces", **fields))

    def rows(self):
        if not monitor.db_path().exists():
            return {}
        socket = os.environ["TMUX"].split(",")[0]
        with contextlib.closing(sqlite3.connect(monitor.db_path())) as db:
            db.row_factory = sqlite3.Row
            return {row["id"]: dict(row) for row in db.execute(
                "SELECT * FROM agents WHERE socket=? AND state != 'closed'", (socket,))}

    def badge(self):
        return self.published[-1][1][-1]

    def test_completion_question_and_approval_lifecycle(self):
        self.hook("SessionStart", source="startup")
        self.assertEqual(self.badge(), "")
        self.hook("UserPromptSubmit", prompt="Do some work")
        self.assertEqual(self.badge(), "[run]")
        self.hook("PermissionRequest", tool_name="Bash")
        self.assertEqual(self.badge(), "[approve]")
        self.hook("PostToolUse", tool_name="Bash")
        self.assertEqual(self.badge(), "[run]")
        self.hook("PreToolUse", tool_name="request_user_input")
        self.assertEqual(self.badge(), "[question]")
        self.hook("PostToolUse", tool_name="request_user_input")
        self.assertEqual(self.badge(), "[run]")
        self.hook("PostToolUse", tool_name="request_user_input_async")
        self.assertEqual(self.badge(), "[question]")
        self.hook("UserPromptSubmit", prompt="My answer")
        self.hook("Stop")
        self.assertEqual(self.badge(), "[done]")
        self.hook("Interrupt")
        self.assertEqual(self.badge(), "[paused]")

    def test_window_label_tracks_idle_sessions_and_clears_after_last_session(self):
        def active():
            return [args[-1] for _, args in self.published
                    if "@codex_active" in args][-1]

        self.hook("SessionStart", source="startup")
        self.assertEqual(self.badge(), "")
        self.assertEqual(active(), "1")
        with patch.dict(os.environ, TMUX_PANE="%2"):
            self.hook("SessionStart", session="other", source="startup")
        self.hook("SessionEnd")
        self.assertEqual(active(), "1")
        with patch.dict(os.environ, TMUX_PANE="%2"):
            self.hook("Interrupt", session="other")
            self.assertEqual(active(), "1")
            self.assertEqual(self.badge(), "[paused]")
            monitor.clear()
        self.assertEqual(active(), "0")
        self.assertEqual(self.badge(), "")

    def test_subagent_task_and_activity_are_grouped_under_parent(self):
        self.hook("UserPromptSubmit")
        self.hook("SubagentStart", agent_id="child", agent_type="explorer")
        self.hook("PostToolUse", tool_name="spawn_agent",
                  tool_input={"message": "Investigate the parser"},
                  tool_response=json.dumps({"agent_id": "child"}))
        self.hook("PreToolUse", session="child", tool_name="Bash")
        self.assertEqual(self.rows()["child"]["parent"], "root")
        self.assertEqual(self.rows()["child"]["task"], "Investigate the parser")
        self.assertEqual(self.rows()["child"]["detail"], "Bash")
        self.hook("PermissionRequest", session="child", tool_name="Bash")
        self.hook("PreToolUse", tool_name="apply_patch")
        self.assertEqual(self.badge(), "[approve]")
        self.hook("SubagentStop", agent_id="child", last_assistant_message="Parser checked")
        self.assertEqual(self.badge(), "[run]")
        self.assertEqual(self.rows()["child"]["detail"], "Parser checked")
        self.assertEqual(self.rows()["child"]["state"], "done")

    def test_panes_and_servers_are_isolated_and_clear_keeps_other_pane(self):
        self.hook("Stop")
        with patch.dict(os.environ, TMUX_PANE="%2"):
            self.hook("PermissionRequest", session="other", tool_name="Bash")
        monitor.clear()
        self.assertNotIn("root", self.rows())
        self.assertEqual(self.badge(), "[approve]")
        with patch.dict(os.environ, TMUX="/tmp/another-server,456,0"):
            self.assertEqual(self.rows(), {})
        with patch.dict(os.environ, TMUX_PANE="%2"):
            monitor.clear()
        self.assertEqual(self.badge(), "")

    def test_unwrapped_shared_daemon_hooks_are_ignored(self):
        with patch.dict(os.environ, CODEX_TMUX_MONITOR=""):
            self.hook("Stop")
        self.assertFalse(monitor.db_path().exists())

    def test_compaction_preserves_attention_and_end_closes_descendants(self):
        self.hook("SubagentStart", agent_id="child", agent_type="worker")
        self.hook("SubagentStart", session="child", agent_id="grandchild")
        self.hook("PermissionRequest", session="grandchild", tool_name="Bash")
        self.hook("SessionStart", source="compact")
        self.assertEqual(self.badge(), "[approve]")
        self.hook("SessionEnd")
        self.assertEqual(self.rows(), {})
        self.assertEqual(self.badge(), "")

    def test_hook_failure_is_passive_and_does_not_decide_permissions(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["monitor", "hook"]), \
                patch.object(sys, "stdin", io.StringIO('{"session_id":"root","hook_event_name":"PermissionRequest"}')), \
                patch.object(monitor, "handle_hook", side_effect=sqlite3.OperationalError("locked")), \
                contextlib.redirect_stdout(output):
            monitor.main()
        self.assertEqual(json.loads(output.getvalue()), {})
        result = subprocess.run([sys.executable, str(MODULE), "hook"],
                                input="invalid JSON", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})

    def test_stored_details_sanitize_control_codes_and_badges_never_use_tool_text(self):
        self.hook("PermissionRequest", tool_name="evil\x1b[31m#{run-shell touch /tmp/NO}")
        self.assertEqual(self.badge(), "[approve]")
        self.assertNotIn("\x1b", self.rows()["root"]["detail"])

    def test_size_cap_applies_to_each_writer_and_rejects_oversized_updates(self):
        self.hook("UserPromptSubmit")
        for _ in range(2):
            db = monitor.connect()
            try:
                page_size = db.execute("PRAGMA page_size").fetchone()[0]
                self.assertEqual(db.execute("PRAGMA max_page_count").fetchone()[0],
                                 monitor.MAX_DB_BYTES // page_size)
                with self.assertRaises(sqlite3.DatabaseError) as failure:
                    with db:
                        db.execute("UPDATE agents SET task=zeroblob(?) WHERE id='root'",
                                   (monitor.MAX_DB_BYTES,))
                self.assertEqual(failure.exception.sqlite_errorcode, sqlite3.SQLITE_FULL)
                self.assertEqual(db.execute("SELECT task FROM agents WHERE id='root'").fetchone()[0], "")
                self.assertLessEqual(monitor.db_path().stat().st_size, monitor.MAX_DB_BYTES)
            finally:
                db.close()

    def test_clear_returns_freed_space_to_disk(self):
        db = monitor.connect()
        try:
            self.assertEqual(db.execute("PRAGMA auto_vacuum").fetchone()[0], 1)
            with db:
                db.executemany("""INSERT INTO agents (id,socket,pane,task,updated)
                    VALUES (?, '/tmp/isolated-codex-test', '%1', ?, ?)""",
                               [(f"agent-{i}", "x" * 2000, time.time()) for i in range(400)])
        finally:
            db.close()
        before = monitor.db_path().stat().st_size
        self.assertGreater(before, 500_000)
        monitor.clear()
        self.assertLess(monitor.db_path().stat().st_size, before // 4)
        self.assertEqual(self.rows(), {})

    def test_legacy_database_migration_preserves_active_records(self):
        self.hook("PermissionRequest", tool_name="Bash")
        legacy = sqlite3.connect(monitor.db_path())
        legacy.execute("PRAGMA auto_vacuum=NONE")
        legacy.execute("VACUUM")
        self.assertEqual(legacy.execute("PRAGMA auto_vacuum").fetchone()[0], 0)
        legacy.close()
        db = monitor.connect()
        try:
            self.assertEqual(db.execute("PRAGMA auto_vacuum").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT state FROM agents WHERE id='root'").fetchone()[0], "approval")
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            db.close()

    def test_expired_and_closed_records_are_pruned_but_live_agents_remain(self):
        self.hook("UserPromptSubmit")
        self.hook("UserPromptSubmit", session="expired")
        self.hook("SessionEnd", session="closed")
        db = monitor.connect()
        try:
            with db:
                db.execute("UPDATE agents SET updated=? WHERE id='expired'",
                           (time.time() - monitor.RETENTION_SECONDS - 1,))
        finally:
            db.close()
        self.hook("PreToolUse", tool_name="Bash")
        self.assertEqual(set(self.rows()), {"root"})
        db = monitor.connect()
        try:
            self.assertEqual(db.execute("SELECT count(*) FROM agents").fetchone()[0], 1)
        finally:
            db.close()

    def test_oversized_legacy_file_is_preserved_without_new_writes(self):
        self.hook("UserPromptSubmit")
        legacy = sqlite3.connect(monitor.db_path())
        with legacy:
            legacy.execute("UPDATE agents SET task=zeroblob(?)", (128 * 1024,))
        legacy.close()
        before = monitor.db_path().read_bytes()
        with patch.object(monitor, "MAX_DB_BYTES", 64 * 1024):
            with self.assertRaises(sqlite3.DatabaseError):
                monitor.connect()
        self.assertEqual(monitor.db_path().read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
