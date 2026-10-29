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
        return {row["id"]: row for row in monitor.snapshot()}

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
        output = "\n".join(monitor.lines_for(list(self.rows().values())))
        self.assertIn("Task: Investigate the parser", output)
        self.assertIn("Parser checked", output)

    def test_panes_and_servers_are_isolated_and_clear_keeps_other_pane(self):
        self.hook("Stop")
        with patch.dict(os.environ, TMUX_PANE="%2"):
            self.hook("PermissionRequest", session="other", tool_name="Bash")
        monitor.clear()
        self.assertNotIn("root", self.rows())
        self.assertEqual(self.badge(), "[approve]")
        with patch.dict(os.environ, TMUX="/tmp/another-server,456,0"):
            self.assertEqual(monitor.snapshot(), [])
        with patch.dict(os.environ, TMUX_PANE="%2"):
            monitor.clear()
        self.assertEqual(self.badge(), "")

    def test_unwrapped_shared_daemon_hooks_are_ignored(self):
        with patch.dict(os.environ, CODEX_TMUX_MONITOR=""):
            self.hook("Stop")
        self.assertFalse(monitor.db_path().exists())

    def test_popup_snapshot_does_not_require_a_pane_environment(self):
        self.hook("UserPromptSubmit")
        with patch.dict(os.environ, TMUX_PANE="", CODEX_TMUX_SOCKET="/tmp/isolated-codex-test"):
            self.assertIn("root", self.rows())

    def test_compaction_preserves_attention_and_end_closes_descendants(self):
        self.hook("SubagentStart", agent_id="child", agent_type="worker")
        self.hook("SubagentStart", session="child", agent_id="grandchild")
        self.hook("PermissionRequest", session="grandchild", tool_name="Bash")
        self.hook("SessionStart", source="compact")
        self.assertEqual(self.badge(), "[approve]")
        self.hook("SessionEnd")
        self.assertEqual(monitor.snapshot(), [])
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

    def test_display_sanitizes_control_codes_and_badges_never_use_tool_text(self):
        self.hook("PermissionRequest", tool_name="evil\x1b[31m#{run-shell touch /tmp/NO}")
        self.assertEqual(self.badge(), "[approve]")
        self.assertNotIn("\x1b", "\n".join(monitor.lines_for(list(self.rows().values()))))


if __name__ == "__main__":
    unittest.main()
