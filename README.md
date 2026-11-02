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
TPM plugins. The configuration skips TPM when it is absent, so reloading still
works; the plugin theme and session restoration require installing the plugins.
Install TPM, reload the configuration, then press **prefix + I** (capital I):

```bash
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
tmux source-file ~/.config/tmux/tmux.conf
```

## Formatting

Run all repository formatters without applying the Home Manager configuration:

```bash
nix-shell --run treefmt
```

Check formatting for CI (exits nonzero if files need formatting, and formats them):

```bash
nix-shell --run 'treefmt --ci'
```

The shell uses your configured `nixpkgs` channel (the setup above uses 24.11).
Home Manager also installs these tools, so after deployment you can run
`treefmt` or `treefmt --ci` directly from the repository root.

| Files                                     | Formatter                |
| ----------------------------------------- | ------------------------ |
| Nix                                       | nixfmt (RFC style)       |
| Python                                    | Ruff format              |
| Lua (including the hidden WezTerm config) | StyLua                   |
| JSON, Markdown, and YAML                  | Prettier                 |
| TOML (formatter configuration)            | Taplo                    |
| tmux `.conf` and `.gitignore`             | Local whitespace cleanup |

The tmux and ignore-file cleanup only removes unescaped trailing whitespace and
normalizes the final newline; it preserves command syntax and indentation.
Embedded shell and tmux strings inside `home.nix` remain literal configuration
content. Local environments, Python caches, and Nix build output are excluded.
Run the commands from the repository root so the local cleanup script is found.

### Pre-commit hook

Enable the formatting hook once per clone:

```bash
nix-shell --run 'pre-commit install'
```

Every commit runs `treefmt --ci` through the Nix shell. If formatting changes
files, the commit stops so you can review and stage the changes, then commit
again. The hook does not stage files automatically. Pre-commit temporarily
stashes unstaged changes while checking the staged content.

Run the hook manually across the repository:

```bash
nix-shell --run 'pre-commit run --all-files'
```

The tools come from the Nix shell; no Home Manager deployment is required.
After deployment, `pre-commit install` and `pre-commit run --all-files` also work
directly. To disable the hook for this clone, run
`nix-shell --run 'pre-commit uninstall'`.

## Verification

```bash
python3 -m unittest discover -s tests -v
nix-instantiate --parse home.nix >/dev/null
git diff --check
```

The Python checks require only the standard library. A full popup check also
requires tmux with popup support and IPython in a disposable test venv.
