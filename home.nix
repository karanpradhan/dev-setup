{ config, pkgs, lib, ... }:

{
  # Basic
  home.username = builtins.getEnv "USER";
  home.homeDirectory = builtins.getEnv "HOME";
  home.stateVersion = "24.11";
  programs.home-manager.enable = true;

  # Packages
  home.packages = with pkgs; [
    python312 rustup git
    fd ripgrep fzf jq curl unzip htop tree xclip wl-clipboard
  ];

  home.sessionVariables = {
    TERM = "xterm-256color";
    COLORTERM = "truecolor";
  };

  # Zsh
  programs.zsh = {
    enable = true;
    enableCompletion = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    shellAliases = {
      ll = "ls -alF";
      gs = "git status";
      vim = "nvim";
      py = "python3";
    };
    initExtra = ''
      # Nix env
      if [ -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/nix.sh"
      fi

      # Prompt
      eval "$(starship init zsh)"
      export EDITOR="nvim"
      export PATH="$HOME/.local/bin:$PATH"

      mkcd() { mkdir -p "$1" && cd "$1"; }

      # Optional local overrides
      [ -f "$HOME/.zshrc.local" ] && source "$HOME/.zshrc.local"
    '';
  };

  # Starship
  programs.starship = {
    enable = true;
    settings = {
      add_newline = false;

      character = {
        success_symbol = "[❯](bold #7aa2f7)"; # blue
        error_symbol   = "[❯](bold #f7768e)"; # red
      };

      directory = {
        style = "bold #9ece6a"; # green
        truncation_length = 3;
      };

      git_branch = { style = "bold #bb9af7"; }; # purple
      git_status = { style = "bold #e0af68"; }; # yellow

      python = {
        format = "[$symbol$pyenv_prefix($version )($virtualenv )]($style)";
        pyenv_version_name = true;
        python_binary = "python3";
        style = "bold #7dcfff"; # cyan
      };

      rust = {
        format = "[$symbol($version )]($style)";
        style = "bold #e0af68"; # yellow
      };

      nodejs = {
        format = "[$symbol($version )]($style)";
        style = "bold #9ece6a"; # green
      };

      cmd_duration = {
        format = "took [$duration]($style) ";
        style = "bold #9ece6a";
      };

      time = {
        disabled = false;
        format = "[$time]($style)";
        style = "bold #565f89"; # muted gray
      };

      # Prompt layout
      format = ''
        $directory$git_branch$git_status$python$rust$nodejs$cmd_duration$character
      '';
      right_format = "$time";
    };
  };

  # Neovim (binary + helpers)
  programs.neovim = {
    enable = true;
    defaultEditor = true;
    viAlias = true;
    vimAlias = true;
    extraPackages = with pkgs; [ git curl unzip ripgrep fd ];
    extraLuaConfig = ''
      -- Basic quality-of-life
      vim.opt.number = true
      vim.opt.mouse = "a"
      vim.opt.clipboard = "unnamedplus"

      -- WSL clipboard bridge: send yanks to Windows and paste from Windows
      if vim.fn.has("wsl") == 1 then
        vim.g.clipboard = {
          name = "WslClipboard",
          copy = {
            ["+"] = "clip.exe",
            ["*"] = "clip.exe",
          },
          paste = {
            ["+"] = "powershell.exe -NoProfile -Command Get-Clipboard",
            ["*"] = "powershell.exe -NoProfile -Command Get-Clipboard",
          },
          cache_enabled = 0,
        }
      end
    '';
  };

  # Tmux
  programs.tmux = {
    enable = true;
    # Handy defaults
    mouse = true;
    clock24 = true;

    # Theme & extras
    extraConfig = ''
      set -g default-terminal "xterm-256color"
      set -as terminal-overrides ',*:Tc'   # enable truecolor

      set -g history-limit 100000
      set -g status-interval 2
      set -g escape-time 0
      setw -g mode-keys vi

      # Tokyo Night-ish colors
      set -g status-style "bg=#1a1b26,fg=#a9b1d6"
      set -g message-style "bg=#1a1b26,fg=#7aa2f7"
      set -g pane-border-style "fg=#3b4261"
      set -g pane-active-border-style "fg=#7aa2f7"
      setw -g mode-style "bg=#283457,fg=#c0caf5"

      # Keep it snappy
      bind-key -n C-a last-window
    '';
  };

  # Git (optional identity)
  programs.git = {
    enable = true;
    userName = "Karan Pradhan";
    userEmail = "karanpradhan@gmail.com";
  };

  # ----- Activation Hooks -----
  # Clone kickstart.nvim once (idempotent)
  home.activation.kickstart = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    NVIM_CFG="$HOME/.config/nvim"
    if [ ! -d "$NVIM_CFG" ]; then
      echo "Cloning kickstart.nvim ..."
      ${pkgs.git}/bin/git clone --depth 1 https://github.com/nvim-lua/kickstart.nvim "$NVIM_CFG"
    else
      echo "kickstart.nvim already exists, skipping clone"
    fi
  '';

  # Ensure Rust toolchain
  home.activation.rustupDefault = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if command -v rustup >/dev/null 2>&1; then
      rustup default stable || true
    fi
  '';
}

