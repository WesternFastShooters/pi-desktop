#!/bin/bash
set -euo pipefail
if [[ $# != 3 ]]; then
  echo 'Usage: bash build.sh /path/Codex.app /path/pi-runtime /path/NEW-output-directory' >&2
  exit 2
fi
[[ $(uname -s) == Darwin ]] || { echo 'Build requires macOS.' >&2; exit 1; }
TOOLS=$(cd "$(dirname "$0")" && pwd)
CODEX_SOURCE=$(cd "$1" && pwd)
PI_SOURCE=$(cd "$2" && pwd)
[[ -f "$CODEX_SOURCE/Contents/Resources/app.asar" && -x "$PI_SOURCE/bin/pi" ]] || { echo 'Expected Codex.app and complete pi-runtime/bin/pi.' >&2; exit 1; }
for package in @injaneity/pi-computer-use pi-chrome-use; do
  [[ -f "$PI_SOURCE/node_modules/$package/package.json" ]] || { echo "Missing bundled Pi tool package: $package" >&2; exit 1; }
done
for cmd in git node npm cargo rustup python3; do command -v "$cmd" >/dev/null || { echo "Missing build tool: $cmd" >&2; exit 1; }; done
[[ ! -e "$3" ]] || { echo 'Choose a new output directory; existing files are never overwritten.' >&2; exit 1; }
mkdir -p "$3"
OUTPUT=$(cd "$3" && pwd)
case $(uname -m) in
  arm64) TARGET=macos-arm64; RUST_TARGET=aarch64-apple-darwin ;;
  x86_64) TARGET=macos-x64; RUST_TARGET=x86_64-apple-darwin ;;
  *) echo 'Unsupported architecture.' >&2; exit 1 ;;
esac
REPO="$OUTPUT/work/codex-host"
git clone https://github.com/BytePioneer-AI/codex-host.git "$REPO"
git -C "$REPO" checkout --detach 08c7d65dddb03a79d5b311d47a0381c299316a3b
git -C "$REPO" apply --check "$TOOLS/codexhost-isolation.patch"
git -C "$REPO" apply "$TOOLS/codexhost-isolation.patch"
rustup target add "$RUST_TARGET"
mkdir -p "$REPO/pi-desktop-packaging/extensions" "$REPO/pi-desktop-packaging/pi-runtime"
for file in build.sh launch.sh pi-tools.sh package.py test_packaging.py README.txt upstream.json codexhost-isolation.patch; do
  cp "$TOOLS/$file" "$REPO/pi-desktop-packaging/$file"
done
cp "$TOOLS/extensions/browser.ts" "$REPO/pi-desktop-packaging/extensions/browser.ts"
cp "$PI_SOURCE/package.json" "$PI_SOURCE/package-lock.json" "$REPO/pi-desktop-packaging/pi-runtime/"
cd "$REPO"
npm ci
node tools/check-boundaries.mjs
cargo fmt --all
cargo test --locked -p codexhost-platform pi_desktop_requires_explicit_installation
cargo test --locked -p codexhost-launcher custom_data_directory_isolates_descriptor
cargo test --locked -p codexhost-launcher forwards_absolute_pi_profile
cargo test --locked -p codexhost-launcher pi_desktop_custom_install_reaches_macos_discovery
# The payload builder imports compiled workspace contracts on module load.
npm run build:typescript
npm exec -- vitest run --config tests/vitest.config.js packages/renderer-extension/test/pi-desktop-defaults.test.ts packages/renderer-extension/test/agent-selection-state.test.ts packages/host-runtime/test/index.test.ts packages/host-runtime/test/pi-side-context.test.ts
# Use upstream's payload builder without invoking the stock DMG packager.
node --input-type=module - "$TARGET" "$OUTPUT/payload-location.txt" <<'NODE'
import { writeFile } from 'node:fs/promises';
import { prepareReleasePayload } from './scripts/release/prepare-payload.mjs';
import { releaseTarget } from './scripts/release/targets.mjs';
const result = await prepareReleasePayload({ target: releaseTarget(process.argv[2]) });
await writeFile(process.argv[3], result.payloadRoot + '\n');
NODE
PAYLOAD=$(cat "$OUTPUT/payload-location.txt")
python3 "$TOOLS/package.py" "$CODEX_SOURCE" "$PI_SOURCE" "$PAYLOAD" "$OUTPUT"
echo "Built $OUTPUT/Pi Desktop.dmg. Run the coexistence checks in README.txt before relying on it."
