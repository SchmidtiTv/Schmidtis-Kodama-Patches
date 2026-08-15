"""Typed provider namespace registration for the application composition root."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from .contracts import (
    MusicCatalogProvider,
    MusicLibraryProvider,
    PlaylistProvider,
    SongCreditsProvider,
    SongStatisticsProvider,
)


class ProviderNamespace(StrEnum):
    """Stable top-level namespaces exposed by :class:`ProviderCollection`."""

    YOUTUBE = "youtube"
    SONG_STATISTICS = "song_statistics"


class DuplicateProviderNamespaceError(RuntimeError):
    """Raised during composition when a namespace is registered twice."""


class MissingProviderNamespaceError(RuntimeError):
    """Raised during composition when a required namespace was not registered."""


@dataclass(frozen=True, slots=True)
class YoutubeCapabilities:
    """Independently implemented capabilities grouped below ``youtube``."""

    catalog: MusicCatalogProvider
    library: MusicLibraryProvider | None = None
    playlists: PlaylistProvider | None = None
    credits: SongCreditsProvider | None = None


@dataclass(frozen=True, slots=True)
class SongStatisticsCapabilities:
    """Registration bundle for the provider-neutral song statistics capability."""

    provider: SongStatisticsProvider


type CapabilityBundle = YoutubeCapabilities | SongStatisticsCapabilities

_CapabilityBundleT = TypeVar("_CapabilityBundleT", bound=CapabilityBundle)


class ProviderCollection:
    """Register provider namespaces and resolve them during application composition.

    ``use()`` belongs exclusively in the application composition root. Routes and
    services receive resolved capability protocols instead of this collection.
    """

    def __init__(self) -> None:
        self._namespaces: dict[ProviderNamespace, CapabilityBundle] = {}

    def use(self, capabilities: CapabilityBundle) -> None:
        """Register a capability bundle without constructing clients or performing I/O."""

        namespace = self._namespace_for(capabilities)
        if namespace in self._namespaces:
            raise DuplicateProviderNamespaceError(
                f"Provider namespace '{namespace}' is already registered."
            )
        self._namespaces[namespace] = capabilities

    @property
    def youtube(self) -> YoutubeCapabilities:
        """Resolve the required YouTube capability namespace."""

        return self._resolve(ProviderNamespace.YOUTUBE, YoutubeCapabilities)

    @property
    def song_statistics(self) -> SongStatisticsProvider:
        """Resolve only the narrow song-statistics capability."""

        capabilities = self._resolve(
            ProviderNamespace.SONG_STATISTICS,
            SongStatisticsCapabilities,
        )
        return capabilities.provider

    @staticmethod
    def _namespace_for(capabilities: CapabilityBundle) -> ProviderNamespace:
        if isinstance(capabilities, YoutubeCapabilities):
            return ProviderNamespace.YOUTUBE
        if isinstance(capabilities, SongStatisticsCapabilities):
            return ProviderNamespace.SONG_STATISTICS
        raise TypeError(f"Unsupported capability bundle: {type(capabilities).__name__}")

    def _resolve(
        self,
        namespace: ProviderNamespace,
        capability_type: type[_CapabilityBundleT],
    ) -> _CapabilityBundleT:
        try:
            capabilities = self._namespaces[namespace]
        except KeyError:
            raise MissingProviderNamespaceError(
                f"Required provider namespace '{namespace}' was not registered "
                "during application construction."
            ) from None
        if not isinstance(capabilities, capability_type):
            raise TypeError(f"Provider namespace '{namespace}' has an invalid capability bundle.")
        return capabilities
