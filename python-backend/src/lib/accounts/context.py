"""Narrow, dynamically evaluated active-profile context."""

from typing import Protocol

from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.profiles.profile import Profile

from .errors import AuthenticationRequiredError


class ActiveMusicProfile(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def is_local(self) -> bool: ...


class SessionActiveMusicProfile:
    """Expose only the current profile identity required by account services."""

    def __init__(self, session: YoutubeMusicSession, profiles: Profile) -> None:
        self._session = session
        self._profiles = profiles

    @property
    def name(self) -> str:
        name = self._session.state.current_profile
        if not name:
            raise AuthenticationRequiredError()
        return name

    @property
    def is_local(self) -> bool:
        return self._profiles.is_local(self.name)
