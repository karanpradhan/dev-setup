# 🌌 WSL2 Developer Environment (Nix + Home Manager)

A reproducible, themed developer setup for **WSL2 (Ubuntu/Debian)** using **Nix** and **Home Manager**.  
Includes **Python + uv**, **Rust**, **Node.js**, **Neovim**,
**Zsh + Starship**, and **tmux**. The tmux configuration and persistent IPython
scratchpad use **Rosé Pine Moon** colors. A separate **Tokyo Night** preset is
provided for Windows Terminal. The shell sets `EDITOR=hx`; install Helix separately
if it is not already available.

---

## ⚙️ Setup Instructions

### 0. Git clone

```bash

git clone git@github.com:karanpradhan/dev-setup.git
cd dev-setup

```

### 1. Install dependencies
```bash
sudo apt update && sudo apt install -y curl git zsh xz-utils

```

### 2. Install Nix

```bash
sh <(curl -L https://nixos.org/nix/install) --no-daemon
. "$HOME/.nix-profile/etc/profile.d/nix.sh"
```

### 3. Install Home Manager Channel

```bash
nix-channel --add https://nixos.org/channels/nixos-24.11 nixpkgs
nix-channel --add https://github.com/nix-community/home-manager/archive/release-24.11.tar.gz home-manager
nix-channel --update
```

### 4. Install Home Manager

```bash
nix-shell '<home-manager>' -A install
```

### 5. Add Configuration

```bash
mkdir -p ~/.config/home-manager
cp home.nix ~/.config/home-manager/home.nix
cp -R tmux ~/.config/home-manager/

```

### 6. Apply Configuration

```bash
home-manager switch
exec zsh
```

If the scratchpad files already exist as unmanaged files in `~/.config/tmux/`,
back them up before applying, or use `home-manager switch -b before-scratchpad`
with a fresh backup suffix. Home Manager deploys the helper and binding and loads
the binding from its generated tmux configuration. An existing `~/.tmux.conf`
must source `~/.config/tmux/tmux.conf` for that managed configuration to load.
No additional `~/.tmux.conf` is needed on a fresh installation.

For an already running tmux server, load just the new binding without restarting:

```bash
tmux source-file ~/.config/tmux/python-pad.conf
```

### 7. (Optional) Make ZSH your default shell

```bash
# Add nix zsh to /etc/shells
echo "$HOME/.nix-profile/bin/zsh" | sudo tee -a /etc/shells

# Change login shell
chsh -s "$HOME/.nix-profile/bin/zsh"

```

### 8. Copy over windows-terminal-tokyo.json to your WSL2 Profile

### 9. Manually install kickstart neovim

```bash

git clone https://github.com/nvim-lua/kickstart.nvim.git "${XDG_CONFIG_HOME:-$HOME/.config}"/nvim
```

## CLI reminders

Run `tools` for a cheat sheet of the installed CLI tools, examples, and fzf
shortcuts. Run `tools --tip` for a single random reminder. Interactive terminals
show one tip each day; the date is stored under
`$XDG_STATE_HOME/cli-tools/last-tip` (default `~/.local/state/cli-tools/last-tip`).
Tabs and tmux panes share this record. Shells opened at exactly the same time
may both display a tip.

To disable automatic tips, add `export CLI_TIPS=0` to `~/.zshrc.local`.
The `tools` command remains available. Scripts and noninteractive shells do not
show automatic tips.

## Global Codex tmux integration

With Codex CLI 0.165.0 or later, **prefix + a** opens a live popup of tracked
sessions and subagents across the current tmux server. It shows each agent's
state, latest observed tool, and task when the spawn hook exposes it. Completed
subagents remain visible until their parent session closes. The popup refreshes
every second; use **q**, **Escape**, or **Ctrl+Q** to close it, and arrows or j/k
to scroll. Closing the popup leaves Codex running.

Window tabs show `[run]`, `[approve]`, `[question]`, `[done]`, or `[paused]`.
Approval and question badges take priority, including requests from subagents.
A new prompt or resumed tool activity clears that session's attention badge;
exiting Codex clears its pane's records. Merely visiting a window does not
acknowledge a pending request. Multiple panes in a window share its badge.

Home Manager installs user-level hooks at `~/.codex/hooks.json`. After applying
the configuration, open a new Zsh shell, start `codex`, and use **`/hooks` to
review and trust the hooks**. Changed hook definitions may require another trust
review. Existing sessions must be restarted to pick up the integration. If you
already have hooks, merge their definitions before applying; do not overwrite
them. These hooks only observe events and never approve or deny commands.

The Zsh `codex` function uses `--no-daemon` in interactive tmux terminals so hook
events inherit the correct pane instead of the shared server's first terminal.
Outside tmux it invokes Codex normally. `command codex` bypasses the wrapper and
is not tracked. The integration does not enable subagent delegation; it displays
agents when you ask Codex to use them.

State lives in `$XDG_STATE_HOME/codex-tmux/state.sqlite3` (default
`~/.local/state/codex-tmux/state.sqlite3`), separate from Codex's private database.
It stores short task summaries and tool names, not full transcripts or shell
commands. Each agent has one row that is updated in place. Hooks remove records
older than seven days and closed sessions; CLI exit removes its pane's records.
SQLite FULL auto-vacuum returns freed pages to disk on commit. Every writer
connection enforces a **16 MiB limit on the main database file**. Temporary
rollback journals and migration files can use additional space while writing.
At the limit, monitoring updates can be skipped; Codex work and approval behavior
continue normally. Live records are not evicted to make room. Older databases
are migrated automatically; a legacy file already above the cap is left intact
and monitoring writes are skipped until it is cleaned up separately.

Hooks track supported tool events rather than streaming the agent's
internal reasoning. Approval alerts can briefly appear during automatic approval
review. Unsupported question/MCP elicitation paths cannot be detected reliably.

For an existing tmux server, load the binding and tab formats without restarting:

```bash
tmux source-file ~/.config/tmux/codex-monitor.conf
```

The installation copy of `tmux/` from step 5 is required for this integration as
well as the Python scratchpad. See the [official Codex hook documentation](https://learn.chatgpt.com/docs/hooks)
for supported events and the hook trust workflow.

## Python scratchpad

Press **prefix + p** (normally **Ctrl+B**, then **p**) to open a persistent
IPython popup. It uses the nearest `.venv` or `venv` in the current folder or its
parents, stopping at a Git root or the home directory. It does not create or
activate environments automatically.

Create an environment and install IPython explicitly when needed:

```bash
uv venv --prompt my-env .venv
uv pip install --python .venv/bin/python ipython
```

The popup shows the environment's configured name (from `pyvenv.cfg`, otherwise
`.venv` or `venv`) and full path. Missing environments or missing IPython produce
a warning; the launcher never installs packages or falls back to global Python.

- **Ctrl+Q:** hide the popup and keep variables in memory.
- **Prefix + p:** reopen the same environment's session.
- **Ctrl+D:** exit IPython; the next opening starts a fresh session.

Sessions are separate per environment and host tmux socket. Persistence lasts
while the background process runs, including when the popup is hidden; variables
do not survive a reboot. The popup uses a separate tmux server so its appearance
and detach shortcut do not change the main session. Underlying panes continue
running while the overlay is open, but tmux pauses their visual refresh.

The Rosé Pine Moon tmux theme and session restoration configuration reference
TPM plugins. Install TPM and use its install binding (prefix + I) if desired:

```bash
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
```

## Verification

```bash
python3 -m unittest discover -s tests -v
nix-instantiate --parse home.nix >/dev/null
git diff --check
```

The Python checks require only the standard library. A full popup check also
requires tmux with popup support and IPython in a disposable test venv.
