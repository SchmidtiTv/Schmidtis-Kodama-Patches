#!/usr/bin/env zsh
# Build a release-ready Kodama macOS app, including the Python sidecar.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="aarch64-apple-darwin"
ICON_STYLE="${KODAMA_APP_ICON_STYLE:-adaptive}"

fail() {
  print -u2 -- "Error: $*"
  exit 1
}

case "${1:-}" in
  "") ;;
  --adaptive-icon) ICON_STYLE="adaptive" ;;
  --classic-icon) ICON_STYLE="classic" ;;
  *) fail "Usage: $0 [--adaptive-icon|--classic-icon]" ;;
esac

[[ "$ICON_STYLE" == "adaptive" || "$ICON_STYLE" == "classic" ]] || \
  fail "KODAMA_APP_ICON_STYLE must be 'adaptive' or 'classic'."

[[ "$(uname -s)" == "Darwin" ]] || fail "This script must run on macOS."
[[ "$(uname -m)" == "arm64" ]] || fail "Only Apple Silicon is supported by the bundled macOS sidecar."
command -v node >/dev/null || fail "Node.js 22 or newer is required."
command -v npm >/dev/null || fail "npm is required."
command -v uv >/dev/null || fail "uv is required."

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
(( NODE_MAJOR >= 22 )) || fail "Node.js 22 or newer is required (found $(node --version))."
cd "$ROOT_DIR"

print -- "==> Installing frontend dependencies"
npm install

print -- "==> Building Composer"
(
  cd composer
  npx --yes pnpm@9 install --frozen-lockfile
  npx --yes pnpm@9 build
)

print -- "==> Installing Python build dependencies"
uv sync --project "$ROOT_DIR/python-backend" --locked --group build

print -- "==> Building the Python sidecar"
(
  cd python-backend
  uv run --locked --group build pyinstaller kodama-server-aarch64-apple-darwin.spec \
    --distpath ../src-tauri/binaries \
    --workpath build_tmp/kodama-server-aarch64-apple-darwin
)
chmod +x "$ROOT_DIR/src-tauri/binaries/kodama-server-aarch64-apple-darwin"

print -- "==> Building the macOS app ($ICON_STYLE icon)"
CI=true KODAMA_APP_ICON_STYLE="$ICON_STYLE" npm run build:macos:dmg

print -- "Build complete. Artifacts:"
print -- "  $ROOT_DIR/src-tauri/target/$TARGET/release/bundle/dmg/Kodama-branded.dmg"

print -- "==> Opening Build Artifacts"
open -R "$ROOT_DIR/src-tauri/target/$TARGET/release/bundle/dmg/Kodama-branded.dmg"
