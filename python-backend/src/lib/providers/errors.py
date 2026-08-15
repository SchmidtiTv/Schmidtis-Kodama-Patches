"""Safe errors raised by implementations at provider boundaries."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar


class ProviderError(Exception):
    """Base error safe to translate outside a provider adapter."""

    message: ClassVar[str] = "Provider operation failed."

    def __init__(self) -> None:
        super().__init__(self.message)


class ProviderUnavailableError(ProviderError):
    """The external provider could not be reached or is unavailable."""

    message = "Provider is unavailable."


class ProviderAuthenticationError(ProviderError):
    """The provider rejected the current authentication state."""

    message = "Provider authentication failed."


class ProviderResponseError(ProviderError):
    """The provider returned an unsuccessful or malformed response."""

    message = "Provider returned an invalid response."


@contextmanager
def translate_provider_errors(
    upstream_errors: type[Exception] | tuple[type[Exception], ...],
    provider_error: type[ProviderError] = ProviderResponseError,
) -> Iterator[None]:
    """Convert selected vendor exceptions without retaining sensitive details."""

    try:
        yield
    except ProviderError:
        raise
    except upstream_errors:
        raise provider_error() from None
