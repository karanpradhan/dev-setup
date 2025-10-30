# 🌌 WSL2 Developer Environment (Nix + Home Manager + Tokyo Night)

A reproducible, themed developer setup for **WSL2 (Ubuntu/Debian)** using **Nix** and **Home Manager**.  
Includes **Python**, **Rust**, **Neovim (kickstart.nvim)**, **Zsh + Starship**, and **Tmux**, all styled with the **Tokyo Night** color scheme.

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

```

### 6. Apply Configuration

```bash
home-manager switch
exec zsh
```

### 7. (Optional) Make ZSH your default shell

```bash
# Add nix zsh to /etc/shells
echo "$HOME/.nix-profile/bin/zsh" | sudo tee -a /etc/shells

# Change login shell
chsh -s "$HOME/.nix-profile/bin/zsh"

```

### 8. Copy over windows-terminal-tokyo.json to your WSL2 Profile

