"""Validation shared by playlist Mix routes."""


def _valid_playlist_id(playlist_id: str) -> bool:
    return bool(playlist_id.strip()) and len(playlist_id) <= 256
