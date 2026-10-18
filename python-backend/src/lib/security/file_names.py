"""Validation for request-supplied names that become file names."""

from typing import cast


class UnsafeFileNameError(ValueError):
    """A name that would leave its directory or is not a plain file stem."""


def is_safe_file_stem(name: object) -> bool:
    """Whether ``name`` is a plain file stem that stays inside its directory.

    Checked on every platform the same way: a backslash is a separator on Windows, and a
    leading dot would address the parent directory or a hidden marker file.
    """
    return (
        isinstance(name, str)
        and bool(name)
        and not name.startswith(".")
        and not any(character in name for character in "/\\\0:")
    )


def require_safe_file_stem(name: object) -> str:
    """Return ``name`` when it is a plain file stem, else raise ``UnsafeFileNameError``."""
    if not is_safe_file_stem(name):
        raise UnsafeFileNameError(f"unsafe file name: {name!r}")
    return cast(str, name)
