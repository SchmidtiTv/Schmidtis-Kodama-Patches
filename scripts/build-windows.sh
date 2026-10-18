#!/usr/bin/env bash
# Cross-build Kodama's Windows x64 NSIS installer on macOS.
#
# Mirrors the Windows job of the former release workflow, minus the bgutil PO-token
# generator: this fork's backend never starts it, so it would only ship ~96 MB of
# node_modules. Two macOS-specific twists:
#   * The Python sidecar is a PyInstaller exe, and PyInstaller cannot cross-compile. It is
#     built with Windows Python running under Wine inside an amd64 Docker container
#     (scripts/windows-sidecar.Dockerfile), unless a sidecar exe already exists or is passed with --sidecar.
#   * The Rust app is cross-compiled with cargo-xwin (clang-cl + lld-link + the MSVC SDK it
#     downloads), and the installer is made with Homebrew's makensis.
#
# Usage: scripts/build-windows.sh [--sidecar PATH] [--rebuild-sidecar] [--update-installer]
#   --sidecar PATH       use this prebuilt kodama-server exe instead of building one
#   --rebuild-sidecar    rebuild the sidecar even if src-tauri/binaries already has one
#   --update-installer   also build the slim in-app update installer (no node.exe)
#
# Signing: TAURI_SIGNING_PRIVATE_KEY (+ _PASSWORD) in the environment produce the updater
# .sig files. Without them the installer is built unsigned and without updater artifacts.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET=x86_64-pc-windows-msvc
NODE_VERSION=22.18.0
SIDECAR_IMAGE=kodama-windows-sidecar

SIDECAR="$ROOT/src-tauri/binaries/kodama-server-$TARGET.exe"
RESOURCES="$ROOT/src-tauri/resources"
NSIS_OUT="$ROOT/src-tauri/target/$TARGET/release/bundle/nsis"
OUT="$ROOT/src-tauri/target/$TARGET/release/bundle/out"

sidecar_source=""
rebuild_sidecar=false
update_installer=false

while [ $# -gt 0 ]; do
  case "$1" in
    --sidecar) sidecar_source="${2:?--sidecar needs a path}"; shift 2 ;;
    --rebuild-sidecar) rebuild_sidecar=true; shift ;;
    --update-installer) update_installer=true; shift ;;
    -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/kodama-windows.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

check_prerequisites() {
  step "Checking prerequisites"
  [ "$(uname -s)" = Darwin ] || die "this script cross-builds from macOS"

  local missing=()
  for tool in npm jq curl cargo rustup cargo-xwin makensis; do
    command -v "$tool" >/dev/null || missing+=("$tool")
  done

  # Homebrew's llvm and lld are keg-only; clang-cl, llvm-rc and lld-link live there.
  local prefix
  for formula in llvm lld; do
    prefix="$(brew --prefix "$formula" 2>/dev/null || true)"
    [ -d "$prefix/bin" ] && PATH="$prefix/bin:$PATH"
  done
  export PATH
  for tool in clang-cl lld-link llvm-rc llvm-lib; do
    command -v "$tool" >/dev/null || missing+=("$tool")
  done

  if [ ${#missing[@]} -gt 0 ]; then
    die "missing tools: ${missing[*]}
Install them with:
  brew install llvm lld nsis jq
  cargo install --locked cargo-xwin"
  fi

  rustup target list --installed | grep -qx "$TARGET" \
    || die "Rust target $TARGET is not installed. Run: rustup target add $TARGET"
}

prepare_sidecar() {
  step "Preparing the Python sidecar"
  mkdir -p "$(dirname "$SIDECAR")"

  if [ -n "$sidecar_source" ]; then
    [ -f "$sidecar_source" ] || die "sidecar not found: $sidecar_source"
    cp "$sidecar_source" "$SIDECAR"
    echo "Using the sidecar from $sidecar_source"
    return
  fi
  if [ -f "$SIDECAR" ] && ! $rebuild_sidecar; then
    echo "Reusing $SIDECAR (pass --rebuild-sidecar to rebuild it)"
    return
  fi

  command -v docker >/dev/null || die "docker is needed to build the Windows sidecar under Wine"
  docker info >/dev/null 2>&1 || die "the Docker daemon is not running (start Docker Desktop or colima)"
  [ -d "$ROOT/composer/dist" ] \
    || die "composer/dist is missing; the sidecar bundles it. Build it with: (cd composer && pnpm install --frozen-lockfile && pnpm build)"

  # The universal uv lock carries Windows markers, so this export resolves the exact locked
  # Windows wheels for pip inside the container.
  local build_dir="$ROOT/python-backend/build_tmp"
  mkdir -p "$build_dir"
  (cd "$ROOT/python-backend" && uv export --locked --group build --no-dev --no-hashes \
    --no-emit-project --format requirements-txt -o build_tmp/windows-requirements.txt) >/dev/null

  echo "Preparing the Wine build image (cached after the first run)..."
  docker build -q --platform linux/amd64 -t "$SIDECAR_IMAGE" \
    -f "$ROOT/scripts/windows-sidecar.Dockerfile" "$ROOT/scripts" >/dev/null

  echo "Running PyInstaller under Wine (amd64 emulation, this takes a while)..."
  docker run --rm --platform linux/amd64 \
    -v "$ROOT:/src" -w /src/python-backend "$SIDECAR_IMAGE" sh -euc "
      wine python -m pip install --disable-pip-version-check -q -r build_tmp/windows-requirements.txt
      wine python -m PyInstaller --noconfirm kodama-server-$TARGET.spec \
        --distpath ../src-tauri/binaries \
        --workpath build_tmp/kodama-server-$TARGET
    "
  [ -f "$SIDECAR" ] || die "PyInstaller finished without producing $SIDECAR"
}

download_node() {
  step "Fetching node.exe v$NODE_VERSION"
  mkdir -p "$RESOURCES"
  local base="https://nodejs.org/dist/v$NODE_VERSION"
  local expected
  expected="$(curl -fsSL "$base/SHASUMS256.txt" | awk '$2 == "win-x64/node.exe" { print $1 }')"
  [ -n "$expected" ] || die "could not read the node.exe checksum from $base/SHASUMS256.txt"

  if [ -f "$RESOURCES/node.exe" ] && [ "$(shasum -a 256 "$RESOURCES/node.exe" | cut -d' ' -f1)" = "$expected" ]; then
    echo "node.exe is already present and verified"
    return
  fi
  curl -fL --progress-bar "$base/win-x64/node.exe" -o "$WORK/node.exe"
  [ "$(shasum -a 256 "$WORK/node.exe" | cut -d' ' -f1)" = "$expected" ] || die "node.exe checksum mismatch"
  mv "$WORK/node.exe" "$RESOURCES/node.exe"
}

# Build-only config overrides go to a temp file passed with --config, so the tracked
# tauri.windows.conf.json stays untouched.
write_config() {
  local without_node="$1" config="$2"
  jq -n --argjson signed "$signed" --argjson slim "$without_node" '
    {}
    | if $slim then .bundle.resources["resources/node.exe"] = null else . end
    | if $signed then . else .bundle.createUpdaterArtifacts = false end
  ' > "$config"
}

tauri_build() {
  local config="$1"
  # audiopus_sys picks its build path from the host's cfg, so on macOS it would compile a
  # macOS libopus. Point it at the static Windows opus.lib that ships inside the crate.
  local opus_dir
  opus_dir="$(cd "$ROOT" && cargo metadata --format-version 1 --manifest-path src-tauri/Cargo.toml \
    --filter-platform "$TARGET" | jq -r '.packages[] | select(.name == "audiopus_sys") | .manifest_path')"
  [ -n "$opus_dir" ] || die "could not locate the audiopus_sys crate"
  opus_dir="$(dirname "$opus_dir")/msvc/x64"

  rm -f "$NSIS_OUT"/*_x64-setup.exe "$NSIS_OUT"/*_x64-setup.exe.sig
  (cd "$ROOT" && LIBOPUS_NO_PKG=1 LIBOPUS_STATIC=1 LIBOPUS_LIB_DIR="$opus_dir" \
    npx tauri build --runner cargo-xwin --target "$TARGET" --bundles nsis --config "$config")
}

collect() {
  local suffix="$1" setup
  setup="$(ls "$NSIS_OUT"/*_x64-setup.exe 2>/dev/null | head -1 || true)"
  [ -n "$setup" ] || die "no installer found in $NSIS_OUT"
  local dest="$OUT/$(basename "$setup" _x64-setup.exe)_x64-$suffix.exe"
  cp "$setup" "$dest"
  [ -f "$setup.sig" ] && cp "$setup.sig" "$dest.sig"
  echo "$dest"
}

check_prerequisites

signed=true
if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  signed=false
  warn "TAURI_SIGNING_PRIVATE_KEY is not set; building without updater signatures"
fi

prepare_sidecar
download_node

step "Installing frontend dependencies"
(cd "$ROOT" && npm install --no-audit --no-fund)

rm -rf "$OUT"
mkdir -p "$OUT"

step "Building the Windows installer"
write_config false "$WORK/tauri.full.json"
tauri_build "$WORK/tauri.full.json"
full="$(collect setup)"

if $update_installer; then
  # In-app updates fetch node.exe on their own (since alpha.38), so latest.json points at
  # this smaller installer while the full setup stays the download for new installs.
  step "Building the slim update installer (no node.exe)"
  write_config true "$WORK/tauri.slim.json"
  tauri_build "$WORK/tauri.slim.json"
  slim="$(collect update)"
  full_size="$(stat -f %z "$full")"
  slim_size="$(stat -f %z "$slim")"
  echo "full: $full_size bytes, slim: $slim_size bytes"
  # node.exe adds about 22 MB to the compressed installer.
  [ "$slim_size" -lt $((full_size - 15000000)) ] || die "the slim installer still seems to contain node.exe"
fi

step "Done"
ls -la "$OUT"
