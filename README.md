<div align="center">
  <img width="210" height="48" alt="Kodama Logo Full" src="https://github.com/user-attachments/assets/e003560b-1760-4657-a8fc-454195293937" />
  <p>An unofficial desktop player for YouTube Music.</p>

  [![Fork](https://img.shields.io/badge/repository-fork-a855f7?style=for-the-badge)](https://github.com/SchmidtiTv/Kodama)
  [![Platform](https://img.shields.io/badge/platform-Windows_%7C_macOS-0078d4?style=for-the-badge)](https://github.com/SchmidtiTv/Kodama)
  [![Tauri](https://img.shields.io/badge/Tauri-2.x-24c8db?style=for-the-badge&logo=tauri&logoColor=white)](https://tauri.app)
  [![License](https://img.shields.io/badge/license-AGPL_v3-3da639?style=for-the-badge)](LICENSE)
</div>

---

> This is a fork of [KiyoshiTheDevil/Kodama](https://github.com/KiyoshiTheDevil/Kodama), not the original project.

## Features

- Synced lyrics with word- and syllable-level timing, plus Unison community lyrics.
- A Lyrics Composer for creating and editing lyrics.
- Crossfade, a built-in visualizer, remote control, and an OBS overlay.
- Offline downloads, Discord Rich Presence, and Last.fm scrobbling.
- Search, playlists, artist pages, profiles, and a keyboard-first desktop interface.

> A Google account and YouTube Premium are not required, though some content may be unavailable because of Premium restrictions.

## Changes from the original repository

This section tracks changes in this fork's [`main`](https://github.com/SchmidtiTv/Kodama/tree/main)
branch relative to the original repository's [`upstream/master`](https://github.com/KiyoshiTheDevil/Kodama/tree/master).
It does **not** use this fork's separate `master` branch as the baseline. See the
[live comparison](https://github.com/KiyoshiTheDevil/Kodama/compare/master...SchmidtiTv:main) for the complete diff.

### Fork-specific improvements

- Replaced frontend-managed playback with a native Rust engine that owns playback state, queue
  transitions, seeking, crossfades, media controls, Discord Rich Presence, Last.fm, and remote and
  overlay updates.
- Persisted playback sessions per profile, restoring the track and queue after restart without
  automatically resuming audio.
- Added customizable player-bar controls and fully configurable, cross-platform keyboard shortcuts.
- Added a Spotlight-style global search with unified song, album, artist, and playlist results.
- Added song and playlist radio with queue deduplication, plus fallbacks for search, radio, and
  custom lyrics when a primary source is unavailable.
- Added artist band-member details with portraits and Wikipedia links, concurrent lookup, and
  on-disk caching.
- Added SQLite-backed metadata caching and incremental loading for liked songs and playlist audio
  counterparts, including visible playlist-resolution progress.
- Added per-profile recommendation caching, automatic restoration of the last active profile, and
  clearer loading, retry, empty, and error states across data-driven views.
- Added an IPv4-first network preference, Italian localization, enabled Spanish and Russian
  localizations, and macOS-specific sidebar search and Command-key defaults.
- Reduced visualizer overhead by running audio analysis only while it is visible, and added a
  development menu for inspecting and controlling native playback.

### Reliability fixes

- Corrected resume, restart, current-track selection, crossfade seeking, volume persistence, and
  stale native-player state synchronization.
- Made streaming more resilient to expired or rejected signed URLs, avoided duplicate source
  resolution, and preferred audio-capable variants in library and playlist results.
- Hardened authentication, including brand-account sign-in and actionable embedded-login errors.
- Protected yt-dlp browser-cookie persistence with authenticated encryption and an encryption key
  stored in the operating system's credential vault.
- Isolated profile-scoped playlist caches and stopped playback cleanly when changing profiles.
- Improved lyrics-provider matching, credit-line filtering, synchronization labels, provider
  preference migration, and the Lyrics Browser's Composer action.
- Fixed artwork fallbacks, narrow-layout behavior, hover flicker, modal exit animations, duplicate
  development listeners, overlay traffic, macOS traffic-light placement, and shared-song handoff.

## For developers

### Prerequisites

- [Node.js](https://nodejs.org/) 18 or later
- [Rust](https://rustup.rs/) stable
- [uv](https://docs.astral.sh/uv/) (manages Python 3.12 and backend dependencies)

### Setup

```bash
git clone https://github.com/SchmidtiTv/Kodama.git
cd Kodama

npm install

cd python-backend
uv sync --locked --group dev
cd ..
```

Optionally authenticate a YouTube account:

```bash
cd python-backend
uv run python setup_auth.py
cd ..
```

### Browser-cookie security

Browser cookies used by yt-dlp are never persisted as plaintext. Kodama stores authenticated
ciphertext in the backend cache and protects its encryption key with the operating system's
credential vault through Python's `keyring` library. If no secure credential backend is available,
the cookies remain in memory for the current process instead of being written to disk.

During development, the encrypted cookie file is `.cache/browser-cookies.enc` under
`python-backend/`. A legacy `browser_cookies.txt` file is encrypted and removed automatically when
the backend starts. The `.cache/` directory is ignored by Git and must not be committed.

### Run and verify

```bash
# Start the desktop app in development mode
npm run tauri dev

# Create a production build
npm run tauri build

# Run frontend checks
npm run lint
npm run build
```

## License

Kodama is licensed under the **[GNU Affero General Public License v3.0](LICENSE)** (AGPL-3.0).
You may use, study, modify, and redistribute it, provided derivative works remain under the same
license and their source is made available. The bundled lyrics Composer is also licensed under
AGPL-3.0.

## Disclaimer

Kodama is an **unofficial** client and is **not affiliated with or endorsed by YouTube or Google**.
It relies on the unofficial YouTube Music API and is provided for personal use, as-is and without
warranty. Use at your own risk.
