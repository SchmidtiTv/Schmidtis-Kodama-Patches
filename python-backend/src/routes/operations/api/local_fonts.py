"""Local system fonts (Windows Registry)."""

from typing import Protocol, cast

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint


class WindowsRegistry(Protocol):
    HKEY_LOCAL_MACHINE: object
    HKEY_CURRENT_USER: object

    def OpenKey(self, hive: object, path: str) -> object: ...
    def EnumValue(self, key: object, index: int) -> tuple[str, object, object]: ...
    def CloseKey(self, key: object) -> None: ...


@blueprint.route("/api/local-fonts")
def api_local_fonts() -> RouteResponse:
    """Return sorted list of font family names installed on the system (Windows Registry)."""
    families = set()
    style_suffixes = (
        " Bold Italic",
        " Bold",
        " Italic",
        " Regular",
        " Light Italic",
        " Light",
        " Medium Italic",
        " Medium",
        " SemiBold Italic",
        " SemiBold",
        " Demi Bold",
        " Demi",
        " Black Italic",
        " Black",
        " Thin Italic",
        " Thin",
        " ExtraLight Italic",
        " ExtraLight",
        " ExtraBold Italic",
        " ExtraBold",
        " Condensed Bold Italic",
        " Condensed Bold",
        " Condensed Italic",
        " Condensed",
        " Narrow Bold",
        " Narrow",
    )
    try:
        import winreg

        registry = cast("WindowsRegistry", winreg)
        reg_paths = [
            (registry.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
            (registry.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        ]
        for hive, path in reg_paths:
            try:
                key = registry.OpenKey(hive, path)
                index = 0
                while True:
                    try:
                        name, _, _ = registry.EnumValue(key, index)
                        name = name.split("(")[0].strip()
                        for suffix in style_suffixes:
                            if name.lower().endswith(suffix.lower()):
                                name = name[: len(name) - len(suffix)].strip()
                                break
                        if name:
                            families.add(name)
                        index += 1
                    except OSError:
                        break
                registry.CloseKey(key)
            except Exception:
                pass
    except Exception:
        pass
    return jsonify(sorted(families))
