from unittest.mock import patch

from src.lib.music.lyrics import LyricsService


class _Response:
    def __init__(self, payload: object, *, text: str = "", ok: bool = True) -> None:
        self._payload = payload
        self.text = text
        self.ok = ok

    def json(self) -> object:
        return self._payload


class LyricsProviderTests:
    def test_paxsenix_picker_requires_matching_title_and_artist(self) -> None:
        songs: list[dict[str, object]] = [
            {
                "id": 1,
                "name": "Bad Apple (from Lovelight)",
                "artists": [{"name": "Masayoshi Minoshima"}],
                "duration": 220_000,
            },
            {
                "id": 2,
                "name": "Bad Apple!!",
                "artists": [{"name": "nomico"}],
                "duration": 219_000,
            },
        ]

        selected = LyricsService._pick_paxsenix_song(songs, "Bad Apple!!", "nomico", 220_000)

        assert selected is not None
        assert selected["id"] == 2

    def test_portato_extracts_unescaped_qrc(self) -> None:
        response = _Response(
            {
                "lyrics": (
                    '<Lyric_1 LyricContent="[0,1000]Hello(0,500)' ' &amp; world(500,500)\\n" />'
                )
            }
        )

        with patch("src.lib.music.lyrics.requests.get", return_value=response):
            result = LyricsService._lookup_portato("Song", "Artist", "Album", "180", "portato")

        assert result is not None
        assert result["source"] == "Better Lyrics Portato"
        qrc = result["qrc"]
        assert isinstance(qrc, str)
        assert "& world" in qrc
