# Upstream integration — 2026-09-06

Compared fork `e4a8924` with upstream master `96f33b8`, using merge-base
`753c734a29e56073c3de2fa208301e9863ebec2e`. The user approved the integration,
including one-second fullscreen idle hiding and hover protection.

The merge records upstream ancestry while applying the reviewed changes to the
fork's existing modules. Upstream's monolithic entry points are not restored.

## Integrated changes

| Upstream commits | Behavior | Fork implementation |
| --- | --- | --- |
| `23c573c` | Library playlists without artwork no longer break parsing | `python-backend/pyproject.toml` and `uv.lock`: ytmusicapi 1.12.2 |
| `5310886`, `6a75451` | OLED uses dark HeroUI tokens and matching card surfaces | `src/shared/lib/theme.js`, app stylesheet, main/overlay/mini-player entry points |
| `9cdee4f`, `0fe1256`, `6a4ec13`, `90088f3`, `a4f5cbf`, `ea5d26e` | Aligned round sidebar controls, scroll fades and no scrollbar arrows | App sidebar, existing Spotlight Search launcher, settings sidebar, app stylesheet |
| `24ca4be`, `830aedf` | Sidebar labels and dropdown widths follow UI zoom | Shared sidebar tooltip, root zoom property, existing menu call sites |
| `ce3d17c`, `880b38d`, `a76d87e` | Sharper Home artwork, optional Speed Dial and larger pager targets | Existing Home view and appearance settings context; image retries and Home caching retained |
| `d2d800d` | Show backend dependency versions in Settings | Thin `/status` route, runtime version reader, cancellable settings hook using the shared API client |
| `f1ec5ad`, `43f3f3e` | Windows fullscreen transitions without intermediate unmaximize | Native window placement/monitor handling in `src-tauri/src/window.rs` |
| `59ec3aa` through `fb80bee`, plus `a85a231` | Fullscreen idle hiding, hover protection and reliable cursor styling | App-owned fullscreen hook and tested idle controller, shared keyboard/button transition, document-wide cursor CSS |
| `4aa51ab`, `8d55383`, `bafe10c` | Smaller website hero image and corrected rounded buttons | Existing documentation site and WebP image with PNG fallback |

The fullscreen shortcut no longer invokes native commands from a React state updater.
Clicks always reveal controls, even without pointer movement. Repeated toggle requests
are ignored while a native transition is pending. The Windows command runs asynchronously
so waiting for its main-thread geometry operation does not itself block the UI thread.

## Preserved or inapplicable changes

- `791c7cd`: upstream removes an incorrect equalizer/Video Sync warning. Our native
  equalizer has no such warning, and Video Sync already uses native audio. No duplicate
  equalizer window, storage format or playback implementation was introduced.
- `52fa497`: retained the fork's version numbers, update manifest and release configuration;
  upstream's signed binaries are not substituted for fork releases. Added accurate local
  unreleased notes instead of overwriting fork release history.
- Temporary fullscreen diagnostics and cursor experiments that upstream subsequently removed
  are not ported; only the final behavior is integrated.
- The top-level `composer/` directory is excluded from this work.
- Existing untracked `out/` and `src-tauri/resources/` are excluded from the merge.
- Redundant tooltip commentary and verbose upstream debugging narratives are omitted.
  Short comments explaining zoom coordinates, pointer jitter and native geometry remain.

## Verification

- Backend pytest: **159 passed**.
- Fullscreen idle and theme unit tests: **6 passed**.
- Frontend production build: **passed** (bundle-size warning).
- macOS `cargo check --locked`: **passed** (existing Objective-C macro/dependency warnings).
- `git diff --check`: **passed**.
- Changed Python files: Black **passed**. Focused Ruff **passed** with `CPY001` and
  `PT009` excluded (repository copyright policy and existing unittest assertion convention).
- Repository ESLint: four existing errors in `src/shared/i18n/i18n.js`; confirmed against
  the unchanged HEAD version. No new ESLint errors.
- Repository Python gates remain failing: Black reports 86 files needing formatting;
  Ruff reports extensive existing violations; Pyrefly reports 258 errors, none in the
  changed Python modules or added tests.
- Browser smoke tests were attempted. The normal runner hit a service-startup race
  (`Dev server not reachable`). A retry found ports 1421 and 9847 occupied and stopped
  without terminating the running application. Added OLED and Speed Dial browser
  regression cases remain unverified.
- Windows fullscreen behavior requires testing on Windows; only the macOS Rust target
  is installed on this machine. No live native fullscreen round-trip was verified.
