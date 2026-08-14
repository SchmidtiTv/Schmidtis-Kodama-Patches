"""Installed-package version lookup for debug reporting."""


def package_version(name: str) -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return "—"
