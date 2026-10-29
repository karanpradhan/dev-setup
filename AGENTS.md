# Project guidance

This repository contains personal WSL2 developer configuration managed by Nix
Home Manager. `home.nix` defines packages, shell configuration, Starship, and tmux.
The tmux theme and Python scratchpad use Rosé Pine Moon colors; the Windows
Terminal JSON is a separate Tokyo Night preset.

## Editing and installation

- Keep reusable configuration here. Do not commit virtual environments, Python
  history, generated Nix output, credentials, private keys, or local backups.
- `~/.config/home-manager/home.nix` is the deployed copy. When asked to sync live
  settings, compare it with this repository and preserve unrelated user changes.
- Files under `tmux/` are deployed through `xdg.configFile` in `home.nix`. Keep
  their relative paths working when the configuration is copied for installation.
- Do not edit generated files in `/nix/store` or replace Home Manager symlinks.
- Updating the repository does not require applying it to the live machine.
  Run `home-manager switch` only when deployment is requested.
- Preserve active tmux sessions and scratchpad variables. Use an isolated tmux
  socket for checks; never kill the user's tmux server to test configuration.

## Scratchpad behavior

- `tmux/python-pad.py` is a dependency-free launcher. Run IPython using the
  detected venv's Python, never an IPython executable from the global PATH.
- Search for `.venv` or `venv` in the current folder and its parents, stopping
  at a Git root or the home directory. Prefer the nearest environment.
- Warn when a venv or IPython is missing. Do not install packages automatically.
- Display the venv's configured prompt name (falling back to its directory name)
  and its full path. Do not substitute the project folder name.
- Prefix + p opens the popup; Ctrl+Q hides it while retaining variables; Ctrl+D
  exits IPython. Scratchpads use isolated tmux servers per venv and host socket.
- Quote shell arguments and escape tmux formats when displaying paths or names.

## Verification

Run these checks for configuration or scratchpad changes:

```sh
python3 -m unittest discover -s tests -v
nix-instantiate --parse home.nix >/dev/null
git diff --check
```

For popup changes, also test opening, Ctrl+Q hiding, reopening with retained
variables, and missing-IPython warnings in an isolated tmux session when possible.
Report which checks ran and any environment limitations. Keep README installation
instructions and keyboard shortcuts consistent with the implementation.
