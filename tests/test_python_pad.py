"""Check environment selection and missing-dependency behavior without tmux."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "tmux/python-pad.py"
SPEC = importlib.util.spec_from_file_location("python_pad", MODULE)
pad = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pad)


class PythonPadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        (self.project / ".git").mkdir()

    def make_venv(self, parent, name=".venv", prompt=None):
        venv = parent / name
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text(
            "" if prompt is None else f"prompt = {prompt}\n"
        )
        (venv / "bin/python").symlink_to(sys.executable)
        return venv

    def test_nearest_venv_from_nested_folder(self):
        self.make_venv(self.project)
        child = self.project / "nested"
        child.mkdir()
        nearest = self.make_venv(child, "venv")
        source = child / "src"
        source.mkdir()
        self.assertEqual(pad.find_venv(source), (child, nearest))

    def test_does_not_cross_git_boundary(self):
        self.make_venv(self.root)
        self.assertIsNone(pad.find_venv(self.project))

    def test_does_not_cross_home_boundary(self):
        self.make_venv(self.root)
        with patch.object(pad.Path, "home", return_value=self.project):
            (self.project / ".git").rmdir()
            self.assertIsNone(pad.find_venv(self.project))

    def test_rejects_incomplete_venv(self):
        venv = self.make_venv(self.project)
        (venv / "pyvenv.cfg").unlink()
        self.assertIsNone(pad.find_venv(self.project))

    def test_configured_name_and_directory_fallback(self):
        venv = self.make_venv(self.project, prompt="'practice-env'")
        self.assertEqual(pad.venv_name(venv), "practice-env")
        (venv / "pyvenv.cfg").write_text("")
        self.assertEqual(pad.venv_name(venv), ".venv")

    def test_dependency_check_uses_venv_python_and_handles_timeout(self):
        venv = self.make_venv(self.project)
        with patch.object(pad.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(pad.has_ipython(venv))
            self.assertEqual(run.call_args.args[0][0], str(venv / "bin/python"))
        with patch.object(pad.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 10)):
            self.assertFalse(pad.has_ipython(venv))

    def test_missing_ipython_warns_without_starting_session(self):
        venv = self.make_venv(self.project, prompt="practice-env")
        with patch.object(pad, "has_ipython", return_value=False), \
                patch.object(pad, "run") as run, \
                patch.object(sys, "argv", ["pad", "--pane", "%1", "--client", "client"]):
            run.return_value.stdout = str(self.project) + "\n"
            pad.main()
        self.assertEqual(run.call_count, 2)
        warning = run.call_args.args
        self.assertIn("display-message", warning)
        self.assertIn("IPython unavailable in practice-env", warning[-1])
        self.assertIn(str(venv), warning[-1])
        self.assertIn("uv pip install --python", warning[-1])

    def test_missing_venv_warns_without_dependency_check(self):
        with patch.object(pad, "has_ipython") as check, \
                patch.object(pad, "run") as run, \
                patch.object(sys, "argv", ["pad", "--pane", "%1", "--client", "client"]):
            run.return_value.stdout = str(self.project) + "\n"
            pad.main()
        check.assert_not_called()
        self.assertIn("no .venv or venv", run.call_args.args[-1])


if __name__ == "__main__":
    unittest.main()
