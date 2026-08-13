"""Authenticated encryption backed by an operating-system credential store."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Protocol

import keyring
from cryptography.fernet import Fernet, InvalidToken
from keyring.errors import KeyringError


class CredentialBackend(Protocol):
    """Narrow keyring interface used by the encrypted store."""

    def get_keyring(self) -> object:
        """Return the selected keyring backend."""

    def get_password(self, service: str, username: str) -> str | None:
        """Return one stored secret."""

    def set_password(self, service: str, username: str, password: str) -> None:
        """Persist one secret."""

    def delete_password(self, service: str, username: str) -> None:
        """Delete one secret."""


class KeyringCredentialBackend:
    """Adapt the keyring module to the narrow credential-store protocol."""

    def get_keyring(self) -> object:
        """Return the selected keyring backend."""
        return keyring.get_keyring()

    def get_password(self, service: str, username: str) -> str | None:
        """Return one stored secret."""
        return keyring.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        """Persist one secret."""
        keyring.set_password(service, username, password)

    def delete_password(self, service: str, username: str) -> None:
        """Delete one secret."""
        keyring.delete_password(service, username)


class EncryptedCredentialStore:
    """Encrypt a small secret file with a key protected by the OS keyring."""

    def __init__(
        self,
        path: Path,
        *,
        service: str,
        account: str,
        credential_backend: CredentialBackend | None = None,
    ) -> None:
        """Configure encrypted storage without opening the OS keyring."""
        self.path = path
        self._service = service
        self._account = account
        self._credential_backend = credential_backend or KeyringCredentialBackend()

    def read(self) -> str | None:
        """Decrypt the stored value, returning ``None`` when unavailable or invalid."""
        if not self.path.is_file():
            return None
        key = self._encryption_key(create=False)
        if key is None:
            return None
        try:
            plaintext = Fernet(key).decrypt(self.path.read_bytes())
            return plaintext.decode("utf-8")
        except (InvalidToken, OSError, UnicodeDecodeError, ValueError):
            return None

    def write(self, value: str) -> bool:
        """Encrypt and atomically persist a value with owner-only permissions."""
        key = self._encryption_key(create=not self.path.exists())
        if key is None:
            return False

        try:
            encrypted = Fernet(key).encrypt(value.encode("utf-8"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as temporary_file:
                    temporary_file.write(encrypted)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
                temporary_path.chmod(0o600)
                temporary_path.replace(self.path)
                self.path.chmod(0o600)
            finally:
                temporary_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            return False
        return True

    def delete(self) -> None:
        """Remove both the encrypted value and its keyring key when possible."""
        with suppress(OSError):
            self.path.unlink(missing_ok=True)
        with suppress(KeyringError):
            self._credential_backend.delete_password(self._service, self._account)

    def _encryption_key(self, *, create: bool) -> bytes | None:
        if not self._has_secure_backend():
            return None
        try:
            stored_key = self._credential_backend.get_password(self._service, self._account)
            if stored_key is None:
                if not create:
                    return None
                stored_key = Fernet.generate_key().decode("ascii")
                self._credential_backend.set_password(
                    self._service,
                    self._account,
                    stored_key,
                )
            key = stored_key.encode("ascii")
            Fernet(key)
        except (KeyringError, UnicodeError, ValueError):
            return None
        return key

    def _has_secure_backend(self) -> bool:
        try:
            priority = getattr(self._credential_backend.get_keyring(), "priority", 0)
            return isinstance(priority, int | float) and priority > 0
        except (KeyringError, RuntimeError):
            return False
