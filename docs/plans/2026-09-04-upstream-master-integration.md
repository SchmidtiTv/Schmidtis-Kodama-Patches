# Upstream master integration

## Goal

Merge `upstream/master` into `main` so its 45 commits become ancestors of this
branch, while preserving Kodama's modular frontend, Flask backend, and native
playback engine.

## Boundaries

- Keep `analytics/worker.js` from this branch. Its metrics protocol is fork
  specific and must not inherit upstream's reporting changes.
- Do not restore legacy `src/App.jsx`, `python-backend/server.py`, or the
  upstream audio-player architecture.
- Resolve the merge with `upstream/master` as a parent, then adapt upstream
  behavior into the owning modules of this branch.

## Adaptations

- Stabilize the translation callback and apply queue virtualizer identity and
  measurement fixes.
- Add the global ten-band equalizer to the native audio source path. Keep the
  existing mix-transition filters independent. Expose it through native state,
  commands, a feature-owned UI window, persistence, and focused tests.
- Consolidate stream, download, export, and video-sync extraction attempts in
  the modular backend. Include a PO-token tier only when the current backend
  has a complete supported token provider.
- Add Last.fm primary-artist and per-track correction rules to native playback
  integration settings. Persist and edit them through the settings feature.
- Add the Discord paused-status preference to native integration settings.
- Extend existing diagnostics with lightweight live measurements; do not add a
  second debug surface or error-capture store.
- Make local sidebar-pin persistence quota-safe and reconcile only library
  playlists known to have been previously observed.
- Apply the JSX undefined-component lint rule and only verified font-scale
  correctness fixes. Keep the current visual system and window chrome.

## Validation

Run focused Rust, frontend, and backend tests for each changed domain, then
`npm run lint`, `npm run build`, applicable Python checks, and `git diff --check`.

## Comment policy

Retain comments that document ownership, threading, persistence, or performance
constraints. Remove only stale or redundant comments in touched code.
