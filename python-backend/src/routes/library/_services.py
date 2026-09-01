"""Shared services for music-library and detail-page routes."""

from typing import cast

from flask import current_app

from src.lib.music.album import Album
from src.lib.music.album_details import AlbumDetailsFinder
from src.lib.music.band_members import BandMemberFinder
from src.lib.music.canvas_artwork import CanvasArtworkFinder
from src.lib.music.credits import SongCreditsCache
from src.lib.music.playlist import Playlist
from src.lib.music.playlist_mix import PlaylistMix
from src.lib.music.mix_analysis import MixAnalysisService
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.profiles.profile import Profile
from src.lib.runtime.cache import CacheSettings
from src.lib.runtime.metadata_cache import MetadataCache


def music_session() -> YoutubeMusicSession:
    return cast(YoutubeMusicSession, current_app.extensions["youtube_music_session"])


def profiles() -> Profile:
    return cast(Profile, current_app.extensions["profile_repository"])


def cache_settings() -> CacheSettings:
    return cast(CacheSettings, current_app.extensions["cache_settings"])


def metadata_cache() -> MetadataCache:
    return cast(MetadataCache, current_app.extensions["metadata_cache"])


def playlist_cache() -> Playlist:
    return cast(Playlist, current_app.extensions["playlist_cache"])


def playlist_mix() -> PlaylistMix:
    return cast(PlaylistMix, current_app.extensions["playlist_mix"])


def mix_analysis_service() -> MixAnalysisService:
    return cast(MixAnalysisService, current_app.extensions["mix_analysis_service"])


def album_cache() -> Album:
    return cast(Album, current_app.extensions["album_cache"])


def album_details_finder() -> AlbumDetailsFinder:
    return cast(AlbumDetailsFinder, current_app.extensions["album_details_finder"])


def band_member_finder() -> BandMemberFinder:
    return cast(BandMemberFinder, current_app.extensions["band_member_finder"])


def song_credits_cache() -> SongCreditsCache:
    return cast(SongCreditsCache, current_app.extensions["song_credits_cache"])


def canvas_artwork_finder() -> CanvasArtworkFinder:
    return cast(CanvasArtworkFinder, current_app.extensions["canvas_artwork_finder"])
