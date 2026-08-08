#!/usr/bin/env python3
"""Create Kodama's Tahoe-compatible branded macOS installer image."""

import argparse
import importlib.util
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKGROUND = REPOSITORY_ROOT / "src-tauri" / "icons" / "dmg-background.png"
DEFAULT_SETTINGS = REPOSITORY_ROOT / "src-tauri" / "dmgbuild-settings.py"
ADAPTIVE_ICON = REPOSITORY_ROOT / "public" / "App-Icons" / "appIconMacos.icon"


def compile_adaptive_app_icon(app: Path) -> None:
    """Make the bundled app use its macOS 26+ adaptive icon asset.

    A .icon directory is source input for Xcode's asset compiler, rather than
    something Finder can load from an app bundle. `actool` turns it into the
    Assets.car catalog that macOS expects at runtime.
    """
    if not ADAPTIVE_ICON.is_dir():
        raise RuntimeError(f"Adaptive icon source is missing: {ADAPTIVE_ICON}")

    resources = app / "Contents" / "Resources"
    subprocess.run(
        [
            "xcrun",
            "actool",
            "--compile",
            str(resources),
            "--platform",
            "macosx",
            "--minimum-deployment-target",
            "26.0",
            str(ADAPTIVE_ICON),
        ],
        check=True,
    )

    info_plist = app / "Contents" / "Info.plist"
    with info_plist.open("rb") as file:
        metadata = plistlib.load(file)

    if metadata.get("CFBundleIconName") != "appIconMacos":
        raise RuntimeError("Kodama.app is missing its appIconMacos icon declaration.")

    metadata.pop("CFBundleIconFile", None)
    with info_plist.open("wb") as file:
        plistlib.dump(metadata, file, sort_keys=False)


def configure_app_icon(app: Path, icon_style: str) -> None:
    """Ship exactly one app-icon system in the final app bundle."""
    resources = app / "Contents" / "Resources"
    info_plist = app / "Contents" / "Info.plist"

    if icon_style == "adaptive":
        compile_adaptive_app_icon(app)
        (resources / "icon.icns").unlink(missing_ok=True)
        shutil.rmtree(resources / "App-Icons", ignore_errors=True)
        return

    (resources / "Assets.car").unlink(missing_ok=True)
    if not (resources / "icon.icns").is_file():
        raise RuntimeError("Classic icon build is missing Contents/Resources/icon.icns.")
    with info_plist.open("rb") as file:
        metadata = plistlib.load(file)
    metadata.pop("CFBundleIconName", None)
    with info_plist.open("wb") as file:
        plistlib.dump(metadata, file, sort_keys=False)


def dmgbuild_command() -> list[str]:
    if importlib.util.find_spec("dmgbuild") is not None:
        return [sys.executable, "-m", "dmgbuild"]

    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "--with", "dmgbuild", "-m", "dmgbuild"]

    raise RuntimeError(
        "dmgbuild is required. Install it with `python3 -m pip install dmgbuild`, "
        "or install uv so this script can provision it automatically."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True, help="Path to the built Kodama.app")
    parser.add_argument("--output", type=Path, required=True, help="Destination .dmg path")
    parser.add_argument(
        "--icon-style",
        choices=("adaptive", "classic"),
        default="adaptive",
        help="Package the macOS 26 adaptive icon or legacy selectable PNG icons.",
    )
    args = parser.parse_args()

    app = args.app.resolve()
    output = args.output.resolve()
    if not app.is_dir() or app.suffix != ".app":
        parser.error(f"--app must be a built .app bundle: {app}")
    if output.exists():
        if not output.is_file() or output.suffix != ".dmg":
            parser.error(f"--output must be a DMG file: {output}")
        output.unlink()

    output.parent.mkdir(parents=True, exist_ok=True)
    configure_app_icon(app, args.icon_style)
    subprocess.run(
        [
            *dmgbuild_command(),
            "--settings",
            str(DEFAULT_SETTINGS),
            "-D",
            f"application={app}",
            "-D",
            f"background={DEFAULT_BACKGROUND}",
            "Kodama",
            str(output),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
