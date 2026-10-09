#!/bin/bash
set -euo pipefail
RES=$(cd "$(dirname "$0")/../.." && pwd)
EXTENSIONS=(--extension "$RES/pi-extensions/browser.ts")
# Read only resource configuration. Never change the user's Pi settings.
LOCAL_COMPUTER_USE=$("$RES/host/runtime/node" --input-type=module - "$PI_CODING_AGENT_DIR/settings.json" <<'NODE'
import { readFile } from 'node:fs/promises';
try {
 const settings = JSON.parse(await readFile(process.argv[2], 'utf8'));
 const sources = (settings.packages ?? []).map(p => typeof p === 'string' ? p : p.source);
 console.log(sources.some(p => typeof p === 'string' && /^npm:@injaneity\/pi-computer-use(?:@|$)/.test(p)) ? '1' : '0');
} catch { console.log('0'); }
NODE
)
if [[ "$LOCAL_COMPUTER_USE" == 1 ]]; then
  # Reuse the existing Pi extension, its helper and its macOS permission grants.
  unset PI_COMPUTER_USE_HELPER_APP_PATH PI_CU_SOCKET_PATH
else
  EXTENSIONS+=(--extension "$RES/pi-runtime/node_modules/@injaneity/pi-computer-use/extensions/computer-use.ts")
fi
exec "$PI_DESKTOP_LOCAL_PI" "${EXTENSIONS[@]}" "$@"
