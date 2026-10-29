"""Exercise the Home Manager Zsh wrapper without launching real Codex sessions."""
import json
import os
from pathlib import Path
import pty
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("zsh"), "zsh is required")
class CodexWrapperTests(unittest.TestCase):
    def run_wrapper(self, args, in_tmux=True):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            stub = path / "codex"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['WRAPPER_RESULT']).write_text(json.dumps(\n"
                "    [sys.argv[1:], os.environ.get('CODEX_TMUX_MONITOR')]))\n"
                "sys.exit(23)\n"
            )
            stub.chmod(0o755)
            monitor = path / "monitor.py"
            monitor.write_text(
                "import os\n"
                "with open(os.environ['WRAPPER_CLEARS'], 'a') as output:\n"
                "    output.write('clear\\n')\n"
            )
            source = (ROOT / "home.nix").read_text()
            function = re.search(r"      codex\(\) \{\n.*?\n      \}", source, re.S)[0]
            function = re.sub(
                r'\$\{pkgs.python311\}/bin/python3 \$\{lib.escapeShellArg .*?\} clear',
                'python3 "$WRAPPER_MONITOR" clear', function,
            )
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"],
                       TMUX="/tmp/wrapper-test,1,0" if in_tmux else "",
                       TMUX_PANE="%1" if in_tmux else "",
                       WRAPPER_RESULT=str(path / "result"),
                       WRAPPER_CLEARS=str(path / "clears"),
                       WRAPPER_MONITOR=str(monitor))
            env.pop("CODEX_TMUX_MONITOR", None)
            master, slave = pty.openpty()
            try:
                result = subprocess.run(
                    ["zsh", "-f", "-i", "-c", function + '\ncodex "$@"', "wrapper", *args],
                    env=env, stdin=slave, stdout=slave, stderr=slave, timeout=10,
                )
            finally:
                os.close(slave)
                os.close(master)
            self.assertEqual(result.returncode, 23)
            clears = (path / "clears").read_text().splitlines() if (path / "clears").exists() else []
            return json.loads((path / "result").read_text()), clears

    def test_agents_uses_shared_server_without_clearing_tracked_sessions(self):
        result, clears = self.run_wrapper(["agents", "--help"])
        self.assertEqual(result, [["agents", "--help"], None])
        self.assertEqual(clears, [])

    def test_plain_codex_keeps_pane_tracking(self):
        result, clears = self.run_wrapper([])
        self.assertEqual(result, [["--no-daemon"], "1"])
        self.assertEqual(clears, ["clear", "clear"])

    def test_interactive_session_keeps_pane_tracking_and_arguments(self):
        args = ["resume", "--last", "a prompt with spaces and # characters"]
        result, clears = self.run_wrapper(args)
        self.assertEqual(result, [["--no-daemon", *args], "1"])
        self.assertEqual(clears, ["clear", "clear"])

    def test_outside_tmux_passes_arguments_through(self):
        result, clears = self.run_wrapper(["hello world"], in_tmux=False)
        self.assertEqual(result, [["hello world"], None])
        self.assertEqual(clears, [])
