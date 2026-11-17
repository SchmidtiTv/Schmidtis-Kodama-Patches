# Upstream integration — 2026-11-17

Recorded upstream master `21a74a2` (through `v1.0.0-alpha.43`) as an ancestor
of the fork's `main` with `git merge -s ours`. The merge-base before this sync
was `95162bb` (`v1.0.0-alpha.42`). No upstream file was applied: the merge
commit's tree is identical to the preceding fork commit.

Purpose: keep the fork from being reported as behind upstream, and make later
syncs show only new upstream commits.

## Integrated changes

None.

## Skipped for now

These 89 upstream commits are not yet adapted to the fork's modular
architecture. Adapting them is a separate task per theme.

| Theme | Upstream commits (examples) | Notes |
| --- | --- | --- |
| Compact / phone layout: bottom sheets, tab capsule, pull-to-refresh, compact queue, lyrics, settings and news | `5a79d1f`, `fee5dc7`, `05df7f5`, `f0ca5fc`, `e84bde5` | Frontend only; port into `src/shared/ui` and `src/features/*`. Best first candidate. |
| Title bar with search, width-adaptive player bar, Onest font | `2ce2c66`, `859bc06`, `44e8318` | Fork already has `shared/ui/title-bar.jsx` and Spotlight search; compare first. |
| Song comments in the queue, autoplay after the queue ends, Last.fm fixes | `a4317a4` | Fork owns autoplay and Last.fm natively (D-1); port only what is missing. |
| Offline lists, queue skips undownloaded songs | `6f7c328` | Fork has its own SQLite metadata cache; port only missing behavior. |
| Bug fixes: no retry flood on failed streams, startup waits for backend, local profiles' public playlists, Node/Brotli CVE | `5f90398`, `c5db998`, `ce70457`, `88c081c` | Check each against fork code; likeliest real fixes. |
| Android port (Chaquopy backend, NewPipeExtractor, media session) | `656681e`, `14513a4`, `4f505f0`, `00399fc`, `src-tauri/gen/android` | Skipped by decision: not shipping Android. Conflicts with native playback (D-1). |
| Browser mode, Web Audio EQ, session keeper, launcher | `a573c7d`, `5975e72`, `84d2ff8`, `ba3c63e` | Skipped by decision: not shipping a browser build. |
| Steam Deck layout | `0dd9e0a`, `092fe63` | Depends on the compact layout. |
| Website, privacy, status, Kodama Next, updater manifest | `docs/*`, `updates/latest.json` | Upstream-owned; not relevant to the fork. |
