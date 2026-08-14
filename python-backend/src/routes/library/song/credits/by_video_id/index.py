"""Scraped song credits and description endpoint."""

import json
import re

import requests
from flask import jsonify

from src.routes.library import blueprint
from src.routes.library._services import song_credits_cache
from src.type_defs import RouteResponse


@blueprint.route("/song/credits/<video_id>")
def get_song_credits(video_id: str) -> RouteResponse:
    # Serve from cache if available
    cached = song_credits_cache().get(video_id)
    if cached is not None:
        return jsonify(cached)
    description = ""
    last_error = ""

    # Use www.youtube.com InnerTube /next — returns full page description (not the
    # truncated YTMusic shortDescription from music.youtube.com/youtubei/v1/player)
    try:
        # Public InnerTube key (same one used by the YouTube web client itself)
        url = (
            "https://www.youtube.com/youtubei/v1/next?key=AIzaSy"
            "AO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        )
        payload = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240726.00.00",
                    "hl": "en",
                    "gl": "US",
                }
            },
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20240726.00.00",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        data = r.json()
        # Path: contents → twoColumnWatchNextResults → results → results → contents[]
        # → videoSecondaryInfoRenderer → attributedDescription.content
        #   OR description.runs[].text
        results = data.get("contents") or {}
        results = results.get("twoColumnWatchNextResults") or {}
        results = results.get("results") or {}
        results = results.get("results") or {}
        contents = results.get("contents") or []
        for item in contents:
            vsir = item.get("videoSecondaryInfoRenderer")
            if not vsir:
                continue
            # Try attributedDescription first (newer YT layout)
            ad = vsir.get("attributedDescription")
            if isinstance(ad, dict):
                description = (ad.get("content") or "").strip()
            # Fall back to description.runs
            if not description:
                runs = (vsir.get("description") or {}).get("runs") or []
                description = "".join(run.get("text", "") for run in runs).strip()
            if description:
                break
    except Exception as e:
        last_error = f"next: {e}"

    # Fallback: scrape www.youtube.com page and extract ytInitialPlayerResponse
    if not description:
        try:
            page_url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            r = requests.get(page_url, headers=headers, timeout=12)
            match = re.search(r"ytInitialPlayerResponse\s*=\s*\{", r.text)
            if match:
                start = match.end() - 1
                depth, end = 0, start
                for i, c in enumerate(r.text[start:]):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            end = start + i + 1
                            break
                page_data = json.loads(r.text[start:end])
                description = (
                    (page_data.get("videoDetails") or {}).get("shortDescription") or ""
                ).strip()
        except Exception as e:
            last_error = f"scrape: {e}"

    result: dict[str, object] = {"description": description}
    if not description and last_error:
        result["error"] = last_error
    song_credits_cache().put(video_id, result)
    return jsonify(result)
