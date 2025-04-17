#!/bin/zsh

# Function to find and activate Python virtual environments
auto_activate_venv() {
  # Check for .venv directory in current or parent directories
  local venv_path=""
  local current_dir="$PWD"

  # First check for .venv in current directory or parent directories
  while [[ "$current_dir" != "" && "$current_dir" != "/" ]]; do
    if [[ -d "$current_dir/.venv" ]]; then
      venv_path="$current_dir/.venv"
      break
    fi
    if [[ -d "$current_dir/venv" ]]; then
      venv_path="$current_dir/venv"
      break
    fi
    current_dir=$(dirname "$current_dir")
  done

  # If we found a venv, activate it
  if [[ -n "$venv_path" ]]; then
    if [[ -f "$venv_path/bin/activate" ]]; then
      echo "🐍 Activating Python virtual environment: $venv_path"
      source "$venv_path/bin/activate"
    fi
  fi
}

# Run the auto-activation function when the shell starts
auto_activate_venv