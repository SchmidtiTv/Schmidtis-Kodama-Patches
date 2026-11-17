# Kodama Agent Guide

These instructions apply to the whole repository. More specific `AGENTS.md`
files extend this guide for their directory trees:

- [`src/AGENTS.md`](src/AGENTS.md) — React frontend architecture and clean-code
  rules.
- [`python-backend/AGENTS.md`](python-backend/AGENTS.md) — Flask backend
  architecture and clean-code rules.

Project memory (status, decisions, milestones, session hand-offs) lives in
[`.ai/`](.ai/AGENTS.md); read it before planning multi-step work.

When instructions differ, follow the guide closest to the file being changed.
Do not bypass a scoped guide by placing code in a less appropriate directory.

## Project Boundaries

Kodama is a Tauri 2 desktop application with a React/JSX frontend and a Python
Flask backend.

| Location          | Responsibility                                      |
|-------------------|-----------------------------------------------------|
| `src/`            | Main React frontend.                                |
| `python-backend/` | Flask API, integrations, and backend domain logic.  |
| `src-tauri/`      | Tauri configuration and native Rust commands.       |
| `composer/`       | Standalone TypeScript/React lyrics composer.        |
| `e2e/`            | Browser and desktop end-to-end tests.               |

Keep these boundaries explicit. Frontend code talks to backend code through
the existing HTTP API and to native code through Tauri commands; it must not
reach into backend or Rust internals.

## Fork History and Upstream Updates

This repository is a heavily refactored fork of
[`KiyoshiTheDevil/Kodama`](https://github.com/KiyoshiTheDevil/Kodama)
(remote `upstream`, branch `master`). The fork's own branch is `main`; its local
`master` is stale and must not be used as a baseline (see
[D-2](.ai/DECISIONS.md)).

### Where the fork came from

Upstream is a monolith: one `src/App.jsx`, one `python-backend/server.py`,
frontend-managed audio. `main` branched from it in July 2026 and replaced that
structure, in roughly this order:

1. **Backend split.** `server.py` became a thin entry point over
   `python-backend/src/{routes,lib}` with service/lib modules per domain
   (accounts, music, providers, integrations, profiles, runtime, security).
2. **Frontend reorganisation.** The flat `src/` tree (`views/`, `ui/`,
   `settings/`, `modals/`, `icons.jsx`, ...) became `src/app` (shell),
   `src/features/*` (one folder per domain) and `src/shared/*` (API, i18n,
   icons, hooks, UI primitives). Settings, overlays and big-picture code were
   split and colocated.
3. **Native Rust playback.** The frontend player was replaced by an engine in
   `src-tauri/src/audio` that owns playback state, queue, crossfade, media
   controls, Discord, Last.fm and remote/overlay updates; the frontend talks to
   it through a central Tauri command bridge ([D-1](.ai/DECISIONS.md)).
4. **Performance and polish.** SQLite metadata caching, per-profile
   recommendation caching, concurrent lyrics providers, lazy overlays, hidden
   panels not rendered, optimised fonts and artwork, once-a-second now-playing
   snapshots.
5. **Tooling and release.** uv-managed Python, stricter lint, local-backend
   hardening (app and LAN remote only), macOS and cross-built Windows
   installers, Font Awesome replaced by a local `Icon` component.

Net effect against the last common point with upstream: about 1,400 files
changed on `main` versus about 360 on upstream.

### How upstream has been integrated so far

Policy is [D-3](.ai/DECISIONS.md): merge `upstream/master` so its commits
become ancestors, but adapt each behavior into the owning modules by hand. The
history therefore contains many `merge: integrate/adapt/record upstream ...`
commits, some of which only record ancestry after a manual port. Never restore
legacy `src/App.jsx`, `python-backend/server.py` or the upstream audio-player
architecture, and keep fork versions, release config and `analytics/worker.js`.

Last integrated upstream release: `v1.0.0-alpha.42`. Upstream has since added
`alpha.43`, a landing page and docs for "Kodama Next", Android project files
(`src-tauri/gen/android`), and updater/privacy changes. About 47 files are
touched on both sides, mostly frontend files `main` has moved.

### Updating from upstream

1. `git fetch upstream` and work on a throwaway branch, never directly on `main`.
2. `git log <last-merge-base>..upstream/master` and `git diff --name-only` to
   list what upstream changed. Ignore `docs/`, `updates/` and
   `src-tauri/gen/android` unless the task says otherwise.
3. `git merge upstream/master`. For a changed file that `main` moved, find the
   new location, read upstream's diff against the old path and re-apply its
   intent in the owning module.
4. Resolve config files (`package.json`, `Cargo.toml`, `tauri.conf.json`,
   `release.yml`) keeping fork versions and release settings.
5. Run the checks below, then document what was integrated, preserved and
   skipped as earlier syncs did in `docs/`.

## Composer Restriction

The `composer/` directory is off limits. Do not inspect, modify, test, or
otherwise include it in task work unless the user explicitly authorizes work
in that directory for the current request.

## Clean-Code Rules

- Put behavior in the narrowest domain that owns it. Prefer extending an
  existing feature or service over creating a generic dumping ground.
- Keep composition and entry-point files thin. They wire modules together;
  they do not own domain behavior.
- Give every module one clear responsibility. Split a module when independent
  reasons to change begin to accumulate, not merely because it is long.
- Prefer small, explicit interfaces and dependency flow over hidden globals,
  cross-domain imports, or duplicated state.
- Reuse existing helpers and conventions before introducing a new abstraction.
  Extract shared code only after it has a stable, genuinely shared purpose.
- Use descriptive domain names. Avoid vague additions such as `utils`,
  `helpers`, `common`, `manager`, or `misc` when a precise name is available.
- Keep functions focused, use guard clauses for invalid states, and avoid deep
  nesting. Comments should explain intent or constraints, not restate code.
- Do not mix refactors with unrelated behavior changes. Preserve public API,
  persisted-data, and IPC contracts unless the task explicitly changes them.
- Validate data at system boundaries and never log secrets, authentication
  headers, tokens, cookies, or private profile data.
- Add or update focused tests for changed behavior. Test public outcomes rather
  than implementation details.
- Leave generated output, caches, dependencies, and build artifacts untouched
  unless the task specifically concerns them.

## Working Method

1. Read the nearest `AGENTS.md` and inspect neighboring code before editing.
2. Identify the owning layer and keep dependencies pointing toward it.
3. Make the smallest coherent change that fully solves the task.
4. Run the most focused checks first, then the relevant project checks.
5. Report checks that could not run and the concrete reason.

## Repository Verification

For frontend or cross-cutting JavaScript changes, run from the repository root:

```sh
npm run lint
npm run build
```

Use `npm run e2e:browser` only when the change affects a covered user flow and
ports 1421 and 9847 are available. Follow the backend guide for Python checks.
