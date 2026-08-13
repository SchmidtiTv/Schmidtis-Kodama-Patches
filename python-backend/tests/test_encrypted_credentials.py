"""Tests for encrypted filesystem secrets backed by a credential store."""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from src.lib.security import EncryptedCredentialStore


class FakeCredentialBackend:
    """In-memory stand-in for an operating-system keyring."""

    def __init__(self, priority: float = 1) -> None:
        self.backend = SimpleNamespace(priority=priority)
        self.passwords: dict[tuple[str, str], str] = {}

    def get_keyring(self) -> object:
        return self.backend

    def get_password(self, service: str, username: str) -> str | None:
        return self.passwords.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.passwords[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.passwords.pop((service, username), None)


class EncryptedCredentialStoreTests:
    """Verify encryption, integrity checks, and fail-closed behavior."""

    def test_round_trip_never_writes_plaintext(self) -> None:
        """Store authenticated ciphertext with owner-only permissions."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.enc"
            backend = FakeCredentialBackend()
            store = EncryptedCredentialStore(
                path,
                service="test-service",
                account="test-account",
                credential_backend=backend,
            )

            assert store.write("SID=secret")
            assert b"SID=secret" not in path.read_bytes()
            assert store.read() == "SID=secret"
            if os.name != "nt":
                assert path.stat().st_mode & 0o777 == 0o600

    def test_tampered_ciphertext_is_rejected(self) -> None:
        """Do not return unauthenticated or corrupted data."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.enc"
            store = EncryptedCredentialStore(
                path,
                service="test-service",
                account="test-account",
                credential_backend=FakeCredentialBackend(),
            )
            assert store.write("SID=secret")
            path.write_bytes(path.read_bytes()[:-1] + b"x")

            assert store.read() is None

    def test_unavailable_keyring_fails_closed(self) -> None:
        """Never create ciphertext with a key outside a secure backend."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.enc"
            store = EncryptedCredentialStore(
                path,
                service="test-service",
                account="test-account",
                credential_backend=FakeCredentialBackend(priority=0),
            )

            assert not store.write("SID=secret")
            assert not path.exists()
