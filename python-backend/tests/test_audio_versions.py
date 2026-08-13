import tempfile
from pathlib import Path

from src.lib.music.audio_versions import iter_preferred_audio_versions, prefer_audio_versions
from src.lib.runtime.metadata_cache import MetadataCache


class FakeWatchPlaylistClient:
    def get_watch_playlist(
        self, videoId: str | None = None, playlistId: str | None = None, limit: int = 25
    ) -> dict[str, object]:
        return {
            "tracks": [
                {
                    "videoId": "audio-id",
                    "title": "Take On Me",
                    "artists": [{"name": "a-ha"}],
                    "album": {"name": "Hunting High and Low", "id": "album-id"},
                    "videoType": "MUSIC_VIDEO_TYPE_ATV",
                }
            ]
        }

    def search(self, query: str, filter: str = "songs", limit: int = 20) -> list[dict[str, object]]:
        return []


class SearchFallbackClient(FakeWatchPlaylistClient):
    def get_watch_playlist(
        self, videoId: str | None = None, playlistId: str | None = None, limit: int = 25
    ) -> dict[str, object]:
        return {"tracks": []}

    def search(self, query: str, filter: str = "songs", limit: int = 20) -> list[dict[str, object]]:
        return [
            {
                "videoId": "search-audio-id",
                "title": "Take On Me",
                "artists": [{"name": "a-ha"}],
                "album": {"name": "Hunting High and Low", "id": "album-id"},
                "duration_seconds": 225,
                "resultType": "song",
                "videoType": "MUSIC_VIDEO_TYPE_ATV",
            }
        ]


class SearchOnlyClient(SearchFallbackClient):
    def __init__(self) -> None:
        self.watch_playlist_calls = 0

    def get_watch_playlist(
        self, videoId: str | None = None, playlistId: str | None = None, limit: int = 25
    ) -> dict[str, object]:
        self.watch_playlist_calls += 1
        raise AssertionError("non-playlist resolution must not request a watch playlist")


class AudioVersionTests:
    def test_video_is_replaced_by_position_matched_audio_counterpart(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me (Official Video)",
            "artists": [{"name": "a-ha"}],
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(FakeWatchPlaylistClient(), "playlist-id", [video])

        assert resolved[0]["videoId"] == "audio-id"

    def test_mismatched_counterpart_is_not_used(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Different Song",
            "artists": [{"name": "a-ha"}],
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(FakeWatchPlaylistClient(), "playlist-id", [video])

        assert resolved[0]["videoId"] == "video-id"

    def test_search_fallback_replaces_an_unresolved_video(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me (Official Video)",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 223,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(SearchFallbackClient(), "playlist-id", [video])

        assert resolved[0]["videoId"] == "search-audio-id"

    def test_search_treats_duration_as_a_ranking_signal(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me (Official Video)",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 180,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(SearchFallbackClient(), "playlist-id", [video])

        assert resolved[0]["videoId"] == "search-audio-id"

    def test_search_normalizes_video_labels_and_artist_prefixes(self) -> None:
        cases = [
            ("DAISIES (Audio)", "DAISIES", "Justin Bieber"),
            ("Anxiety (Visualizer)", "Anxiety", "Doechii"),
            ("Jazeek - AKON (Offizielles Musikvideo)", "AKON", "Jazeek"),
            ("BUNT. - Love Tonight (Lyric Video)", "Love Tonight", "BUNT."),
        ]

        for video_title, audio_title, artist in cases:

            class LabelClient(SearchFallbackClient):
                expected_title = audio_title
                expected_artist = artist

                def search(
                    self, query: str, filter: str = "songs", limit: int = 20
                ) -> list[dict[str, object]]:
                    return [
                        {
                            "videoId": "label-audio-id",
                            "title": self.expected_title,
                            "artists": [{"name": self.expected_artist}],
                            "duration_seconds": 180,
                            "resultType": "song",
                            "videoType": "MUSIC_VIDEO_TYPE_ATV",
                        }
                    ]

            video = {
                "videoId": "video-id",
                "title": video_title,
                "artists": [{"name": artist}],
                "duration_seconds": 240,
                "videoType": "MUSIC_VIDEO_TYPE_OMV",
            }

            resolved = prefer_audio_versions(LabelClient(), None, [video])

            assert resolved[0]["videoId"] == "label-audio-id", video_title

    def test_search_tolerates_feature_credit_title_differences(self) -> None:
        class FeatureCreditClient(SearchFallbackClient):
            def search(
                self, query: str, filter: str = "songs", limit: int = 20
            ) -> list[dict[str, object]]:
                return [
                    {
                        "videoId": "feature-audio-id",
                        "title": "Somebody That I Used To Know (feat. Kimbra)",
                        "artists": [{"name": "Gotye"}],
                        "duration_seconds": 245,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    }
                ]

        video = {
            "videoId": "video-id",
            "title": "Somebody That I Used To Know",
            "artists": [{"name": "Gotye"}],
            "duration_seconds": 244,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(FeatureCreditClient(), None, [video])

        assert resolved[0]["videoId"] == "feature-audio-id"

    def test_search_prefers_the_closest_artist_credits(self) -> None:
        class ArtistCreditClient(SearchFallbackClient):
            def search(
                self, query: str, filter: str = "songs", limit: int = 20
            ) -> list[dict[str, object]]:
                return [
                    {
                        "videoId": "featured-version-id",
                        "title": "The One That Got Away (feat. B.o.B)",
                        "artists": [{"name": "Katy Perry"}],
                        "duration_seconds": 260,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    },
                    {
                        "videoId": "original-id",
                        "title": "The One That Got Away",
                        "artists": [{"name": "Katy Perry"}],
                        "duration_seconds": 228,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    },
                ]

        video = {
            "videoId": "video-id",
            "title": "The One That Got Away (Official Music Video)",
            "artists": [{"name": "Katy Perry"}],
            "duration_seconds": 290,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(ArtistCreditClient(), None, [video])

        assert resolved[0]["videoId"] == "original-id"

    def test_search_rejects_a_cover_despite_an_exact_title(self) -> None:
        class CoverClient(SearchFallbackClient):
            def search(
                self, query: str, filter: str = "songs", limit: int = 20
            ) -> list[dict[str, object]]:
                return [
                    {
                        "videoId": "cover-id",
                        "title": "Take On Me",
                        "artists": [{"name": "Cover Band"}],
                        "duration_seconds": 223,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    }
                ]

        video = {
            "videoId": "video-id",
            "title": "Take On Me",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 223,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(CoverClient(), None, [video])

        assert resolved[0]["videoId"] == "video-id"

    def test_search_preserves_a_named_remix(self) -> None:
        class RemixClient(SearchFallbackClient):
            def search(
                self, query: str, filter: str = "songs", limit: int = 20
            ) -> list[dict[str, object]]:
                return [
                    {
                        "videoId": "base-id",
                        "title": "The Days",
                        "artists": [{"name": "Chrystal"}],
                        "duration_seconds": 230,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    },
                    {
                        "videoId": "remix-id",
                        "title": "The Days (Remix)",
                        "artists": [{"name": "Chrystal"}, {"name": "NOTION"}],
                        "duration_seconds": 233,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    },
                ]

        video = {
            "videoId": "video-id",
            "title": "The Days (Remix)",
            "artists": [{"name": "Chrystal"}, {"name": "NOTION"}],
            "duration_seconds": 233,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(RemixClient(), None, [video])

        assert resolved[0]["videoId"] == "remix-id"

    def test_detected_video_without_video_type_is_resolved(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 223,
            "album": None,
            "thumbnails": [{"width": 400, "height": 225}],
            "videoType": None,
        }

        resolved = prefer_audio_versions(SearchFallbackClient(), "playlist-id", [video])

        assert resolved[0]["videoId"] == "search-audio-id"

    def test_search_accepts_a_matching_non_primary_artist(self) -> None:
        class FeaturedArtistClient(SearchFallbackClient):
            def search(
                self, query: str, filter: str = "songs", limit: int = 20
            ) -> list[dict[str, object]]:
                return [
                    {
                        "videoId": "featured-audio-id",
                        "title": "Take On Me",
                        "artists": [{"name": "Guest"}, {"name": "a-ha"}],
                        "duration_seconds": 230,
                        "resultType": "song",
                        "videoType": "MUSIC_VIDEO_TYPE_ATV",
                    }
                ]

        video = {
            "videoId": "video-id",
            "title": "Take On Me",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 215,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }

        resolved = prefer_audio_versions(FeaturedArtistClient(), None, [video])

        assert resolved[0]["videoId"] == "featured-audio-id"

    def test_search_retries_without_featured_artists(self) -> None:
        class QueryFallbackClient(SearchFallbackClient):
            def __init__(self) -> None:
                self.queries = []

            def search(
                self, query: str, filter: str = "songs", limit: int = 20
            ) -> list[dict[str, object]]:
                self.queries.append(query)
                if "Guest" in query:
                    return []
                return super().search(query, filter=filter, limit=limit)

        video = {
            "videoId": "video-id",
            "title": "Take On Me",
            "artists": [{"name": "a-ha"}, {"name": "Guest"}],
            "duration_seconds": 223,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }
        client = QueryFallbackClient()

        resolved = prefer_audio_versions(client, None, [video])

        assert resolved[0]["videoId"] == "search-audio-id"
        assert client.queries == ["Take On Me a-ha Guest", "Take On Me a-ha"]

    def test_incremental_resolver_yields_batches_in_playlist_order(self) -> None:
        tracks = [
            {
                "videoId": f"video-{index}",
                "title": "Take On Me (Official Video)",
                "artists": [{"name": "a-ha"}],
                "duration_seconds": 223,
                "videoType": "MUSIC_VIDEO_TYPE_OMV",
            }
            for index in range(3)
        ]

        batches = list(
            iter_preferred_audio_versions(SearchFallbackClient(), "playlist-id", tracks, 2)
        )

        assert [len(batch) for batch in batches] == [2, 1]
        assert [track["videoId"] for batch in batches for track in batch] == [
            "search-audio-id",
            "search-audio-id",
            "search-audio-id",
        ]

    def test_non_playlist_tracks_use_search_without_a_watch_playlist(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me (Official Video)",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 223,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }
        client = SearchOnlyClient()

        resolved = prefer_audio_versions(client, None, [video])

        assert resolved[0]["videoId"] == "search-audio-id"
        assert client.watch_playlist_calls == 0

    def test_resolved_counterpart_is_reused_without_another_search(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me (Official Video)",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 223,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }
        with tempfile.TemporaryDirectory() as directory:
            cache = MetadataCache(Path(directory) / "cache.sqlite3")
            first = prefer_audio_versions(SearchOnlyClient(), None, [video], cache)

            class NoNetworkClient(SearchOnlyClient):
                def search(
                    self, query: str, filter: str = "songs", limit: int = 20
                ) -> list[dict[str, object]]:
                    raise AssertionError("cached counterpart should avoid search")

            second = prefer_audio_versions(NoNetworkClient(), None, [video], cache)

        assert first[0]["videoId"] == "search-audio-id"
        assert second[0]["videoId"] == "search-audio-id"

    def test_mismatched_cached_counterpart_is_replaced(self) -> None:
        video = {
            "videoId": "video-id",
            "title": "Take On Me (Official Video)",
            "artists": [{"name": "a-ha"}],
            "duration_seconds": 223,
            "videoType": "MUSIC_VIDEO_TYPE_OMV",
        }
        stale: dict[str, object] = {
            "videoId": "wrong-audio-id",
            "title": "Different Song",
            "artists": [{"name": "a-ha"}],
            "videoType": "MUSIC_VIDEO_TYPE_ATV",
        }
        with tempfile.TemporaryDirectory() as directory:
            cache = MetadataCache(Path(directory) / "cache.sqlite3")
            cache.put_audio_counterpart("video-id", stale)

            resolved = prefer_audio_versions(SearchOnlyClient(), None, [video], cache)

            assert resolved[0]["videoId"] == "search-audio-id"
            cached = cache.get_audio_counterpart("video-id")
            assert cached is not None
            assert cached["videoId"] == "search-audio-id"
