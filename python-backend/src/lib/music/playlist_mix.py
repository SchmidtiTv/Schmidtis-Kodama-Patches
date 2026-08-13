"""Profile-scoped configuration for Kodama playlist Mix sessions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from src.lib.runtime.metadata_cache import MetadataCache


class PlaylistMixConfigurationError(ValueError):
    """Raised when an untrusted Mix configuration does not match the local contract."""


class PlaylistMix:
    """Persist local Mix data without changing the corresponding YouTube Music playlist."""

    _CATEGORY = "playlist_mix"
    _VERSION = 1
    _PRESETS = frozenset({"auto", "fade", "rise", "blend", "wave", "melt", "slam"})
    _VOLUME_CURVES = frozenset({"smooth", "overlap", "cut"})
    _EQ_CURVES = frozenset({"centerBass", "endBassSwap", "threeBandFade", "none"})
    _EFFECTS = frozenset({"none", "lowPass", "highPass"})

    def __init__(self, metadata_cache: MetadataCache) -> None:
        self._metadata_cache = metadata_cache

    def get(self, profile_name: str | None, playlist_id: str) -> dict[str, object]:
        saved = self._metadata_cache.get(self._CATEGORY, self._key(profile_name, playlist_id))
        if saved is None:
            return self._default(playlist_id)
        return self._normalize_saved(playlist_id, saved)

    def update(
        self, profile_name: str | None, playlist_id: str, update: Mapping[str, object]
    ) -> dict[str, object]:
        config = self.get(profile_name, playlist_id)
        for field in update:
            if field not in {"enabled", "smartReorder", "trackOrder", "transitions"}:
                raise PlaylistMixConfigurationError(f"Unsupported Mix field: {field}")

        if "enabled" in update:
            config["enabled"] = self._require_bool("enabled", update["enabled"])
        if "smartReorder" in update:
            config["smartReorder"] = self._require_bool("smartReorder", update["smartReorder"])
        if "trackOrder" in update:
            config["trackOrder"] = self._normalize_track_order(update["trackOrder"])
        if "transitions" in update:
            config["transitions"] = self._normalize_transitions(update["transitions"])

        self._metadata_cache.put(self._CATEGORY, self._key(profile_name, playlist_id), config)
        return config

    def delete(self, profile_name: str | None, playlist_id: str) -> None:
        self._metadata_cache.delete(self._CATEGORY, self._key(profile_name, playlist_id))

    def store_analysis(
        self,
        profile_name: str | None,
        playlist_id: str,
        track_order: list[dict[str, str]],
        track_analysis: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        """Store analyzer-owned fields; callers cannot set these through the HTTP config API."""
        config = self.get(profile_name, playlist_id)
        config["analysisVersion"] = 1
        config["trackOrder"] = self._normalize_track_order(track_order)
        config["trackAnalysis"] = track_analysis
        self._metadata_cache.put(self._CATEGORY, self._key(profile_name, playlist_id), config)
        return config

    def _default(self, playlist_id: str) -> dict[str, object]:
        return {
            "playlistId": playlist_id,
            "version": self._VERSION,
            "enabled": False,
            "analysisVersion": None,
            "smartReorder": False,
            "trackOrder": [],
            "trackAnalysis": {},
            "transitions": [],
        }

    def _normalize_saved(self, playlist_id: str, saved: Mapping[str, object]) -> dict[str, object]:
        """Upgrade the v0 enabled-only record while discarding malformed optional data."""
        config = self._default(playlist_id)
        if isinstance(saved.get("enabled"), bool):
            config["enabled"] = saved["enabled"]
        if isinstance(saved.get("smartReorder"), bool):
            config["smartReorder"] = saved["smartReorder"]
        if saved.get("analysisVersion") == 1:
            config["analysisVersion"] = 1
        if isinstance(saved.get("trackAnalysis"), dict):
            config["trackAnalysis"] = saved["trackAnalysis"]
        try:
            if "trackOrder" in saved:
                config["trackOrder"] = self._normalize_track_order(saved["trackOrder"])
            if "transitions" in saved:
                config["transitions"] = self._normalize_transitions(saved["transitions"])
        except PlaylistMixConfigurationError:
            pass
        return config

    @staticmethod
    def _require_bool(name: str, value: object) -> bool:
        if not isinstance(value, bool):
            raise PlaylistMixConfigurationError(f"{name} must be a boolean")
        return value

    def _normalize_track_order(self, value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            raise PlaylistMixConfigurationError("trackOrder must be an array")
        if len(value) > 10_000:
            raise PlaylistMixConfigurationError("trackOrder is too large")
        normalized: list[dict[str, str]] = []
        instance_ids: set[str] = set()
        for item in value:
            if not isinstance(item, Mapping):
                raise PlaylistMixConfigurationError("trackOrder entries must be objects")
            instance_id = self._require_identifier("trackOrder.instanceId", item.get("instanceId"))
            video_id = self._require_identifier("trackOrder.videoId", item.get("videoId"))
            if instance_id in instance_ids:
                raise PlaylistMixConfigurationError("trackOrder instanceIds must be unique")
            instance_ids.add(instance_id)
            normalized.append({"instanceId": instance_id, "videoId": video_id})
        return normalized

    def _normalize_transitions(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            raise PlaylistMixConfigurationError("transitions must be an array")
        if len(value) > 10_000:
            raise PlaylistMixConfigurationError("transitions is too large")
        normalized: list[dict[str, object]] = []
        transition_ids: set[tuple[str, str]] = set()
        for item in value:
            if not isinstance(item, Mapping):
                raise PlaylistMixConfigurationError("transition entries must be objects")
            from_id = self._require_identifier(
                "fromTrackInstanceId", item.get("fromTrackInstanceId")
            )
            to_id = self._require_identifier("toTrackInstanceId", item.get("toTrackInstanceId"))
            if from_id == to_id:
                raise PlaylistMixConfigurationError("a transition must connect different tracks")
            transition_id = (from_id, to_id)
            if transition_id in transition_ids:
                raise PlaylistMixConfigurationError("transitions must be unique")
            transition_ids.add(transition_id)
            normalized.append(
                {
                    "fromTrackInstanceId": from_id,
                    "toTrackInstanceId": to_id,
                    "preset": self._require_choice("preset", item.get("preset"), self._PRESETS),
                    "bars": self._require_bars(item.get("bars")),
                    "volumeCurve": self._require_choice(
                        "volumeCurve", item.get("volumeCurve"), self._VOLUME_CURVES
                    ),
                    "eqCurve": self._require_choice(
                        "eqCurve", item.get("eqCurve"), self._EQ_CURVES
                    ),
                    "effect": self._require_choice("effect", item.get("effect"), self._EFFECTS),
                    "beatOffsetMs": self._require_beat_offset(item.get("beatOffsetMs")),
                }
            )
        return normalized

    @staticmethod
    def _require_identifier(name: str, value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise PlaylistMixConfigurationError(
                f"{name} must be a non-empty string up to 256 characters"
            )
        return value

    @staticmethod
    def _require_choice(name: str, value: object, allowed: frozenset[str]) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise PlaylistMixConfigurationError(f"{name} is invalid")
        return value

    @staticmethod
    def _require_bars(value: object) -> int:
        if value not in {2, 4, 8}:
            raise PlaylistMixConfigurationError("bars must be 2, 4, or 8")
        return cast("int", value)

    @staticmethod
    def _require_beat_offset(value: object) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not -100 <= value <= 100
        ):
            raise PlaylistMixConfigurationError("beatOffsetMs must be between -100 and 100")
        return float(value)

    @staticmethod
    def _key(profile_name: str | None, playlist_id: str) -> str:
        return json.dumps([profile_name or "default", playlist_id], separators=(",", ":"))
