"""Safe exception translation shared by YouTube account adapters."""

from collections.abc import Callable

import requests

from src.lib.providers.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
)


def call_youtube[ResultT](operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except StopIteration:
        raise
    except ProviderError:
        raise
    except requests.RequestException:
        raise ProviderUnavailableError() from None
    except Exception as error:
        message = str(error)
        if (
            "twoColumnBrowseResultsRenderer" in message
            or "singleColumnBrowseResultsRenderer" in message
            or "authentication" in message.casefold()
            or "unauthorized" in message.casefold()
        ):
            raise ProviderAuthenticationError() from None
        raise ProviderResponseError() from None
