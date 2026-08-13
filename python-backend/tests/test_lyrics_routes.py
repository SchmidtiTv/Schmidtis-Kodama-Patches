from types import SimpleNamespace
from unittest.mock import patch

from route_test_support import RouteTestCase


class LyricsRouteTests(RouteTestCase):
    def test_lyrics_and_unison_routes(self) -> None:
        lyrics = self.client.get("/lyrics?title=Song&artist=Artist&source=auto")
        assert lyrics.json["title"] == "Song"
        assert self.client.post("/romanize-lyrics", json={"lines": ["kana"]}).json[
            "romanizations"
        ] == ["ro:kana"]
        assert self.client.post(
            "/translate-lyrics", json={"lines": ["hi"], "target_lang": "de"}
        ).json["translations"] == ["DE:hi"]

        assert self.client.post(
            "/lyrics/custom", json={"videoId": "vid", "content": "[00:00] hi", "format": "lrc"}
        ).json == {"ok": True}
        assert self.client.get("/lyrics/custom/vid").json["content"] == "[00:00] hi"
        assert self.client.delete("/lyrics/custom/vid").json == {"ok": True}
        assert self.client.get("/lyrics/custom/vid").json == {"found": False}

        versions = self.client.get("/lyrics/unison/versions?videoId=vid&title=Song")
        assert versions.json["versions"][0]["videoId"] == "vid"
        assert self.client.get("/unison/displayname/key").json == {"displayName": "name:key"}

        upstream = SimpleNamespace(
            content=b'{"ok":true}', status_code=201, headers={"Content-Type": "application/json"}
        )
        with patch("src.routes.lyrics._unison.requests.request", return_value=upstream) as request:
            vote = self.client.post("/unison/lyrics/lyr/vote", json={"signed": True})
            report = self.client.post("/unison/lyrics/lyr/report", json={"signed": True})
            nickname = self.client.put("/unison/auth/nickname", json={"signed": True})
            check = self.client.post("/unison/auth/nickname/check", json={"signed": True})
        assert vote.status_code == 201
        assert report.status_code == 201
        assert nickname.status_code == 201
        assert check.status_code == 201
        assert request.call_count == 4
