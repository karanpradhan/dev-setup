"""Check event-driven Codex labels without starting tmux or Codex."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HOOKS = Path(__file__).resolve().parents[1] / 'tmux/program-name.zsh'


@unittest.skipUnless(shutil.which('zsh'), 'zsh is required')
class ProgramNameTests(unittest.TestCase):
    def hook(self, command, function='_tmux_codex_preexec'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'tmux'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TEST_LOG"\n')
            fake.chmod(0o755)
            log = root / 'log'
            environment = dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}',
                               TMUX='test', TMUX_PANE='%42', TEST_LOG=str(log))
            subprocess.run(['zsh', '-f', '-c',
                            'source "$1"; "$2" "$3"',
                            'test', str(HOOKS), function, command],
                           env=environment, check=True)
            return log.read_text().splitlines()

    def test_codex_launchers_and_quoted_paths(self):
        for command in ('codex resume', 'command codex', 'env FOO=bar codex',
                        'node "/path with spaces/codex.js"', '/bin/codex'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command),
                                 ['set-option', '-p', '-t', '%42', '@codex_program', 'codex'])

    def test_unrelated_node_background_job_and_arguments_clear_label(self):
        for command in ('node server.js', 'echo codex', 'codex &',
                        'node server.js /bin/codex.js'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command),
                                 ['set-option', '-pu', '-t', '%42', '@codex_program'])

    def test_prompt_return_clears_label(self):
        self.assertEqual(self.hook('', '_tmux_codex_precmd'),
                         ['set-option', '-pu', '-t', '%42', '@codex_program'])
