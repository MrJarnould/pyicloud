#!/bin/bash
set -e

# Function to log actions
log() {
  echo "SETUP-ZSH: $1"
}

# Install Oh My Zsh if not already installed
if [ ! -d "${HOME}/.oh-my-zsh" ]; then
  log "Installing Oh My Zsh..."
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
  log "Oh My Zsh already installed, skipping."
fi

# Install Powerlevel10k theme
if [ ! -d "${HOME}/.oh-my-zsh/custom/themes/powerlevel10k" ]; then
  log "Installing powerlevel10k theme..."
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "${HOME}/.oh-my-zsh/custom/themes/powerlevel10k"
else
  log "powerlevel10k theme already installed, skipping."
fi

# Install zsh-autosuggestions plugin
if [ ! -d "${HOME}/.oh-my-zsh/custom/plugins/zsh-autosuggestions" ]; then
  log "Installing zsh-autosuggestions..."
  git clone https://github.com/zsh-users/zsh-autosuggestions "${HOME}/.oh-my-zsh/custom/plugins/zsh-autosuggestions"
else
  log "zsh-autosuggestions already installed, skipping."
fi

# Install zsh-syntax-highlighting plugin
if [ ! -d "${HOME}/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting" ]; then
  log "Installing zsh-syntax-highlighting..."
  git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "${HOME}/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting"
else
  log "zsh-syntax-highlighting already installed, skipping."
fi

# Download custom zsh configurations
log "Downloading custom .zshrc..."
curl -sSL https://raw.githubusercontent.com/MrJarnould/container-dotfiles/main/.zshrc -o "${HOME}/.zshrc"

log "Downloading custom .p10k.zsh..."
curl -sSL https://raw.githubusercontent.com/MrJarnould/container-dotfiles/main/.p10k.zsh -o "${HOME}/.p10k.zsh"

# Set up auto-activation of virtual environments
log "Setting up automatic virtual environment activation..."
chmod +x "${PWD}/.devcontainer/auto-activate-venv.sh"

# Add sourcing of auto-activate-venv.sh to .zprofile if not already there
if ! grep -q "auto-activate-venv.sh" "${HOME}/.zprofile" 2>/dev/null; then
  log "Adding auto-activation to .zprofile..."
  echo "# Auto-activate Python virtual environments" >> "${HOME}/.zprofile"
  echo "source ${PWD}/.devcontainer/auto-activate-venv.sh" >> "${HOME}/.zprofile"
else
  log "Auto-activation already in .zprofile, skipping."
fi

log "Setup complete!"