#!/usr/bin/env python3
"""Persistent tmux IPython popup using the project's local virtual environment."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess


def find_venv(folder):
    folder = Path(folder).resolve()
    for root in (folder, *folder.parents):
        for name in (".venv", "venv"):
            candidate = root / name
            if ((candidate / "pyvenv.cfg").is_file()
                    and os.access(candidate / "bin/python", os.X_OK)):
                return root, candidate
        if (root / ".git").exists() or root == Path.home():
            break
    return None


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def venv_name(venv):
    for line in (venv / "pyvenv.cfg").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "prompt" and value.strip():
            return value.strip().strip("\"'")
    return venv.name


def has_ipython(venv):
    try:
        return subprocess.run(
            [str(venv / "bin/python"), "-I", "-c", "import IPython"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pane", required=True)
    parser.add_argument("--client", required=True)
    args = parser.parse_args()
    folder = run("tmux", "display-message", "-p", "-t", args.pane,
                 "#{pane_current_path}", capture_output=True).stdout.strip()
    found = find_venv(folder)
    if found is None:
        run("tmux", "display-message", "-c", args.client,
            "Python pad: no .venv or venv in this project (create one first).")
        return
    root, venv = found
    name = venv_name(venv)
    if not has_ipython(venv):
        install = shlex.join(["uv", "pip", "install", "--python",
                              str(venv / "bin/python"), "ipython"])
        run("tmux", "display-message", "-c", args.client, "-d", "15000",
            f"IPython unavailable in {name} ({venv}). Install with: {install}")
        return
    # A separate server keeps popup detach bindings and options out of the host.
    identity = str(venv) + "\0" + os.environ.get("TMUX", "").split(",")[0] + "\0ipython"
    socket_name = "python-pad-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
    nested = ["tmux", "-L", socket_name, "-f", "/dev/null"]
    environment = os.environ.copy()
    environment.pop("TMUX", None)
    environment.pop("TMUX_PANE", None)
    exists = subprocess.run([*nested, "has-session", "-t", "pad"],
                            env=environment, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode == 0
    if not exists:
        # Run the venv interpreter directly; activation scripts are unnecessary.
        command = shlex.join([str(venv / "bin/python"), "-m", "IPython",
                              "--no-banner", "--no-confirm-exit"])
        run(*nested, "new-session", "-d", "-s", "pad", "-c", str(root),
            "-e", "VIRTUAL_ENV=" + str(venv),
            "-e", "PYTHONSTARTUP=",
            "-e", "PATH=" + str(venv / "bin") + ":" + os.environ.get("PATH", ""),
            command, env=environment)
    # Reapply presentation on opening, including to existing persistent pads.
    options = {
        "status": "2",
        "status-position": "bottom",
        "status-style": "bg=#2a273f,fg=#908caa",
        "status-format[0]": " #[fg=#c4a7e7]" + name.replace("#", "##") + "  #[fg=#908caa]" + str(venv).replace("#", "##"),
        "status-format[1]": " #[fg=#9ccfd8]IPython#[align=right]#[fg=#e0def4]Ctrl+Q#[fg=#908caa] hide   #[fg=#e0def4]Ctrl+D#[fg=#908caa] exit ",
        "window-status-format": "",
        "window-status-current-format": "",
        "pane-border-status": "off",
        "window-style": "bg=#232136,fg=#e0def4",
        "window-active-style": "bg=#232136,fg=#e0def4",
    }
    for option, value in options.items():
        run(*nested, "set-option", "-g", option, value, env=environment)
    run(*nested, "bind-key", "-n", "C-q", "detach-client", env=environment)
    attach = shlex.join(["env", "-u", "TMUX", "-u", "TMUX_PANE",
                         *nested, "attach-session", "-t", "pad"])
    title = "  IPython · " + name.replace("#", "##") + "  "
    run("tmux", "display-popup", "-c", args.client, "-E", "-w", "82%",
        "-h", "72%", "-b", "rounded",
        "-s", "bg=#232136,fg=#e0def4", "-S", "bg=#232136,fg=#c4a7e7",
        "-d", str(root), "-T", title, attach)


if __name__ == "__main__":
    main()
