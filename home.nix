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

      # Optional local overrides
      [ -f "$HOME/.zshrc.local" ] && source "$HOME/.zshrc.local"

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
set -g visual-bell on
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

# Automatic program names
# Extract basename to avoid displaying Nix store paths
setw -g automatic-rename on
setw -g automatic-rename-format '#{b:pane_current_command}'
set -g allow-rename off

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

# Tabs: program + directory (or explicit activity)
set -g window-status-format '#[fg=#908caa,bg=#232136] #I: #{pane_current_command} '

# Active tab: amber highlight
set -g window-status-current-format '#[fg=#232136,bg=#f6c177,bold] #I: #{pane_current_command} #[default]'

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

