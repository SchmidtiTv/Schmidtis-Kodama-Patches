#!/usr/bin/env zsh
# Build release-ready Kodama Linux packages, including the Python sidecar.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="x86_64-unknown-linux-gnu"

fail() {
  print -u2 -- "Error: $*"
  exit 1
}

[[ "$(uname -s)" == "Linux" ]] || fail "This script must run on Linux."
[[ "$(uname -m)" == "x86_64" ]] || fail "Only x86_64 Linux is supported by the bundled Linux sidecar."
command -v node >/dev/null || fail "Node.js 22 or newer is required."
command -v npm >/dev/null || fail "npm is required."
command -v uv >/dev/null || fail "uv is required."
command -v cargo >/dev/null || fail "Rust and Cargo are required."

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
  uv run --locked --group build pyinstaller kodama-server-x86_64-unknown-linux-gnu.spec \
    --distpath ../src-tauri/binaries \
    --workpath build_tmp/kodama-server-x86_64-unknown-linux-gnu
)
chmod +x "$ROOT_DIR/src-tauri/binaries/kodama-server-x86_64-unknown-linux-gnu"

print -- "==> Building Linux packages"
npm run tauri -- build --target "$TARGET" --bundles deb,appimage

print -- "Build complete. Artifacts:"
print -- "  $ROOT_DIR/src-tauri/target/$TARGET/release/bundle/deb/"
print -- "  $ROOT_DIR/src-tauri/target/$TARGET/release/bundle/appimage/"
