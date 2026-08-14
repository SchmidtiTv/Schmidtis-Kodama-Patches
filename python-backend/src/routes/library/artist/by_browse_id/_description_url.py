"""Artist description-source URL lookup."""

from src.routes.library._services import music_session


def _extract_artist_desc_url(browse_id: str) -> str | None:
    """Recover the source URL omitted from ytmusicapi's artist description."""
    try:
        from ytmusicapi.navigation import SECTION_LIST, SINGLE_COLUMN_TAB, find_object_by_key, nav

        response = (
            music_session().get_active_client()._send_request("browse", {"browseId": browse_id})
        )
        results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST)
        shelf = find_object_by_key(results, "musicDescriptionShelfRenderer", is_key=True)
        if not shelf:
            return None
        if isinstance(shelf, dict) and "musicDescriptionShelfRenderer" in shelf:
            shelf = shelf["musicDescriptionShelfRenderer"]
        for run in shelf.get("description", {}).get("runs", []):
            url = ((run.get("navigationEndpoint") or {}).get("urlEndpoint") or {}).get("url")
            if url and "creativecommons" not in url:
                return url
    except Exception:
        pass
    return None
