#!/bin/bash
set -euo pipefail
CONTENTS=$(cd "$(dirname "$0")/.." && pwd)
RES="$CONTENTS/Resources"
DATA="$HOME/Library/Application Support/Pi Desktop"
umask 077
mkdir -p "$DATA/host" "$DATA/codex" "$DATA/electron" "$DATA/pi"
export CODEXHOST_DATA_DIR="$DATA/host"
export CODEX_HOME="$DATA/codex"
export CODEX_ELECTRON_USER_DATA_PATH="$DATA/electron"
# Reuse the real local Pi profile; authentication belongs to Pi, not the shell.
export PI_CODING_AGENT_DIR="$HOME/.pi/agent"
PI_EXECUTABLE="$RES/pi-runtime/bin/pi"
for candidate in "$HOME/.pi/agent/bin/pi" "$HOME/.local/bin/pi" /opt/homebrew/bin/pi /usr/local/bin/pi; do
  if [[ -x "$candidate" ]]; then PI_EXECUTABLE="$candidate"; break; fi
done
export PI_DESKTOP_LOCAL_PI="$PI_EXECUTABLE"
export PI_COMPUTER_USE_HELPER_APP_PATH="$RES/Pi Computer Use.app"
export PI_CU_SOCKET_PATH="$DATA/pi/computer-use.sock"
PI_EXECUTABLE="$RES/pi-tools/bin/pi"
# The official shell supports providers that do not require OpenAI login.
# Native Codex generation is disabled by this local-only provider; sessions use Pi.
if [[ ! -e "$DATA/codex/config.toml" ]]; then
  cat > "$DATA/codex/config.toml" <<'CONFIG'
model = "pi-local"
model_provider = "pi-desktop"
[model_providers.pi-desktop]
name = "Local Pi"
base_url = "http://127.0.0.1:9/v1"
wire_api = "responses"
requires_openai_auth = false
CONFIG
fi
# The browser console has a global default port; this app uses its own logfile.
export CODEXHOST_CONSOLE=0
export PATH="$RES/pi-runtime/bin:$RES/host/runtime:$PATH"
# Reject inherited routing to a separately installed Host or remote session.
unset CODEXHOST_REMOTE_SSH_MANAGED CODEXHOST_HOST_NODE_PATH CODEXHOST_HOST_RUNTIME_PATH
unset CODEXHOST_NPM_PACKAGE_ROOT CODEXHOST_NPM_NODE_PATH CODEXHOST_NPM_CLI_PATH CODEXHOST_NPM_LAUNCHER_PATH
exec "$RES/host/bin/codexhost" launch \
  --custom-install "$RES/Pi Shell.app" \
  --pi "$PI_EXECUTABLE" >> "$DATA/launcher.log" 2>&1
