{ config, pkgs, lib, ... }:

{
  # Basic
  home.username = builtins.getEnv "USER";
  home.homeDirectory = builtins.getEnv "HOME";
  home.stateVersion = "24.11";
  programs.home-manager.enable = true;

  # Packages
  home.packages = with pkgs; [
    gcc gnumake pkg-config
    coreutils bc gawk
    python311 rustup git
    uv
    fd ripgrep fzf curl unzip htop tree xclip wl-clipboard
    nodejs_22
    lua5_1
    luarocks
    eza bat zoxide
    jq yq-go
    lazygit
    httpie gping
    tldr
    btop
    zlib
    gcc.cc.lib
    yazi
    gh
  ];



  nixpkgs = {
  overlays = [
    (final: prev:
      let
        unstable = import (builtins.fetchTarball
          "https://github.com/NixOS/nixpkgs/archive/nixpkgs-unstable.tar.gz")
          { inherit (prev.stdenv) system; };
      in {
        neovim = unstable.neovim;
        neovim-unwrapped = unstable.neovim-unwrapped;
      })
  ];
};

  home.file.".npmrc".text = ''
  prefix=${config.home.homeDirectory}/.npm-global
  '';

  # Keep the persistent IPython scratchpad beside its tmux binding.
  xdg.configFile."tmux/python-pad.py".source = ./tmux/python-pad.py;
  xdg.configFile."tmux/python-pad.conf".source = ./tmux/python-pad.conf;
  xdg.configFile."tmux/program-name.zsh".source = ./tmux/program-name.zsh;
  xdg.configFile."tmux/program-name.conf".source = ./tmux/program-name.conf;
  home.sessionVariables = {

    TERM = "xterm-256color";
    COLORTERM = "truecolor";
    # This tells npm "use ~/.npm-global for globals"

    NPM_CONFIG_PREFIX = "${config.home.homeDirectory}/.npm-global";
  };
  home.sessionPath = [
    "${config.home.homeDirectory}/.npm-global/bin"
    "${pkgs.openssl.dev}/lib/pkgconfig"
  ];

  # Zsh
  programs.zsh = {
    enable = true;
    enableCompletion = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    shellAliases = {
      # ls = "eza";
      ll = "eza -l --icons";
      tree = "eza -T --icons";
      tree2 = "eza -T -L 2 --icons";
      tree3 = "eza -T -L 3 --icons";
      vim = "nvim";
      # cd = "z";
      # cat = "bat";
    };
    initExtra = ''
      # 1. Deduplicate PATH (CRITICAL)
      typeset -U path PATH

      zstyle ':completion:*' use-cache on
      zstyle ':completion:*' cache-path ~/.zsh/cache

      # 3. Autosuggestions: history only (no completion)
      ZSH_AUTOSUGGEST_STRATEGY=(history)

      # 4. Syntax highlighting: fast mode
      ZSH_HIGHLIGHT_HIGHLIGHTERS=(main brackets)
      ZSH_HIGHLIGHT_CHECK_COMMANDS=false

      # Make sure global npm binaries are on PATH
      export PATH="$HOME/.npm-global/bin:$PATH"

      # Update tmux's Codex label only at command start and prompt return.
      source ~/.config/tmux/program-name.zsh

      # Nix env
      if [ -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/nix.sh"
      fi

      # Prompt
      eval "$(starship init zsh)"
      export EDITOR="hx"
      export PATH="$HOME/.local/bin:$PATH"
      export BUN_INSTALL="$HOME/.bun"
      export PATH="$BUN_INSTALL/bin:$PATH"
      export PATH=/home/karan/.opencode/bin:$PATH

      mkcd() { mkdir -p "$1" && cd "$1"; }

      # Keep CLI examples available on demand and show one per day.
      tools() {
        emulate -L zsh
        local -a tips=(
          'fd config — find files with config in their name'
          'rg -n "TODO" — search file contents with line numbers'
          'bat home.nix — read a file with syntax highlighting'
          'll — list files with eza; tree2 — show two directory levels'
          'z setup — jump to a frequently visited directory'
          'lazygit — browse Git changes interactively'
          'yazi — browse files interactively'
          'btop — inspect processes and resource usage'
          'tldr rg — see practical command examples'
          'jq . data.json — pretty-print JSON'
          'Ctrl+R — search command history with fzf'
          'Ctrl+T — select a file path with fzf'
          'Alt+C — select a directory with fzf'
        )
        if [[ "$1" == --tip ]]; then
          print -r -- "CLI tip: $tips[$(( RANDOM % ''${#tips} + 1 ))]"
          print -r -- 'Run tools for all examples. Disable daily tips with CLI_TIPS=0.'
        else
          print -rl -- "''${tips[@]}"
        fi
      }

      _cli_daily_tip() {
        emulate -L zsh
        [[ -o interactive && -t 0 && -t 1 && ''${CLI_TIPS:-1} != 0 ]] || return 0
        local tip_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/cli-tools"
        local today previous
        today=$(command date +%F) || return 0
        [[ -r "$tip_dir/last-tip" ]] && IFS= read -r previous < "$tip_dir/last-tip"
        [[ "$previous" == "$today" ]] && return 0
        command mkdir -p -- "$tip_dir" 2>/dev/null || return 0
        print -r -- "$today" > "$tip_dir/last-tip" 2>/dev/null || return 0
        tools --tip
      }

      # Optional local overrides
      [ -f "$HOME/.zshrc.local" ] && source "$HOME/.zshrc.local"

      _cli_daily_tip
      unfunction _cli_daily_tip

    '';
  };

  programs.zoxide = {
    enable = true;
    enableZshIntegration = true;
  };

  programs.fzf = {
    enable = true;
    enableZshIntegration = true;
  };

  # Starship

programs.starship = {
    enable = true;

    settings = {
      "$schema" = "https://starship.rs/config-schema.json";

      format = ''
        $username$hostname$directory$git_branch$git_state$git_status$cmd_duration$line_break$character
      '';

      directory = {
        style = "blue";
      };

      character = {
        success_symbol = "[❯](purple)";
        error_symbol = "[❯](red)";
        vimcmd_symbol = "[❮](green)";
      };

      git_branch = {
        format = "[$branch]($style)";
        style = "bright-black";
      };

      git_status = {
        format = "[ ($ahead_behind$stashed)]($style)";
        style = "cyan";

        conflicted = "​";
        untracked = "​";
        modified = "​";
        staged = "​";
        renamed = "​";
        deleted = "​";
        stashed = "≡";
      };

      git_state = {
        format = "\\([$state( $progress_current/$progress_total)]($style)\\) ";
        style = "bright-black";
      };

      cmd_duration = {
        format = "[$duration]($style) ";
        style = "yellow";
      };

      # explicitly disable python (extra safety)
      python.disabled = true;

      add_newline = false;

      # Hard safety limits (prevents hangs)
      scan_timeout = 10;
      command_timeout = 50;

      # ------------------------------------------------
      # DISABLE UNUSED / SLOW MODULES
      # ------------------------------------------------
      };
  };


programs.tmux = {
  enable = true;
  mouse = true;
  clock24 = true;
  terminal = "tmux-256color";

 extraConfig = ''


# Rosé Pine Moon tmux configuration
# Optimized for Helix (hx), Zsh, Claude Code, Codex and Nix

# Terminal
set -g default-terminal 'tmux-256color'
set -as terminal-features ',xterm-256color:RGB'
set -g mouse on
set -g history-limit 50000

# Quality of life
set -g visual-bell off
set -g bell-action any
set -g escape-time 10
set -g focus-events on
set -g set-clipboard on

# Avoid noisy activity notifications
setw -g monitor-activity off

# Window and pane numbering
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on

# Single top tab row
set -g status on
set -g status-position top
set -g status-interval 2
set -g status-justify left

# Vi-style copy mode
setw -g mode-keys vi
bind-key -T copy-mode-vi v send-keys -X begin-selection
bind-key -T copy-mode-vi y send-keys -X copy-selection-and-cancel
bind-key -T copy-mode-vi Escape send-keys -X cancel

# Rosé Pine Moon theme
set -g @rose_pine_variant 'moon'
set -g @rose_pine_date_time '%Y-%m-%d'
set -g @rose_pine_directory 'off'
set -g @rose_pine_disable_active_window_menu 'on'
set -g @rose_pine_show_current_program 'on'

# Session persistence
set -g @resurrect-capture-pane-contents 'on'
set -g @continuum-restore 'on'
set -g @continuum-save-interval '15'

# Plugins
set -g @plugin 'rose-pine/tmux'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'

# TPM - install with:
# git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
run-shell '~/.tmux/plugins/tpm/tpm'

# Appearance overrides
set -g status-style 'bg=#232136,fg=#e0def4'
set -g status-left ' '
set -g status-right '#[fg=#9ccfd8]%Y-%m-%d '
set -g status-right-length 40
set -g window-status-separator ' '

# Resolve Node launchers such as Codex, then use the resolved window name in tabs.
source-file ~/.config/tmux/program-name.conf

# Pane borders
set -g pane-border-style 'fg=#44415a'
set -g pane-active-border-style 'fg=#f6c177'

# Publish activity for current window:
# tmux set-option -w @activity 'Editing auth.rs'
#
# Clear activity:
# tmux set-option -wu @activity

# Persistent IPython popup (prefix + p), available in folders with a local venv.
source-file ~/.config/tmux/python-pad.conf
# Remove the former Codex popup binding when reloading an existing server.
unbind-key a

'';
};

  # Git (optional identity)
  programs.git = {
    enable = true;
    userName = "Karan Pradhan";
    userEmail = "karanpradhan@gmail.com";
  };

programs.neovim = {
  enable = true;
  viAlias = true;
  vimAlias = true;
  # extraPython3Packages = ps: with ps; [
      # pynvim         # required for any Python-based Neovim plugin
      # jupyter-client # Molten uses this -> fixes "No module named 'jupyter_client'"
      # ipykernel      # so you can start real Jupyter kernels
  # ];
};



  # ----- Activation Hooks -----

  # Ensure Rust toolchain
  home.activation.rustupDefault = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if command -v rustup >/dev/null 2>&1; then
      rustup default stable || true
    fi
  '';
}

