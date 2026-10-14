# Upstream alpha.42 Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `upstream/master` through `95162bb` while preserving Kodama's native playback engine, modular frontend, fork release identity, and built-in overlay editor.

**Architecture:** Room persistence and connection health stay in the Together feature, while playback restoration is handed to the native Rust engine through the existing Together synchronization command. Localized strings are merged key-by-key into the shared i18n boundary. Upstream history is recorded only after the adapted tree is verified.

**Tech Stack:** React 19, JavaScript modules and Node test runner, Tauri 2/Rust, static website assets.

**Spec:** [`../upstream-sync-2026-10-14.md`](../upstream-sync-2026-10-14.md)

## Global Constraints

- Preserve [.ai decision D-1](../../.ai/DECISIONS.md#d-1-native-rust-engine-owns-playback): Rust owns playback, queue transitions, seeking and Together transport.
- Preserve [.ai decision D-3](../../.ai/DECISIONS.md#d-3-upstream-changes-are-integrated-selectively): do not restore upstream `src/App.jsx` or release configuration.
- Do not inspect or modify `composer/`.
- Keep the built-in overlay editor; do not add Ofuda migration notices.
- Preserve fork versions, updater metadata and release identity.

## Review Focus

- A stale WebSocket that never closes must reconnect without creating two active sockets.
- A remembered room must expire after 24 hours and must be forgotten after an intentional leave or terminal room rejection.
- A returning host must adopt the room track and queue before publishing local state.
- Listener history must not make already-played tracks removable.
- Suggestions must remain visible when the room queue is otherwise empty.

---

### Task 1: Together session state and connection recovery

**Files:**

- Create: `src/features/together/room-session.js`
- Create: `src/features/together/room-session.test.mjs`
- Modify: `src/features/together/together.js`
- Modify: `src/features/together/index.js`

**Interfaces:**

- Produces: pure remembered-room parsing, silence detection and played-history helpers; `resumeLastRoom()`, `reconnect()`, and `finishRoomRestore()`.
- Consumes: existing Together snapshot, room validation and WebSocket lifecycle.

- [x] Write failing tests for fresh/stale remembered rooms, silent connections, bounded played history and duplicate transitions.
- [x] Run `node --test src/features/together/room-session.test.mjs` and confirm the helpers are missing.
- [x] Implement the pure helpers and integrate persistence, reconnect watchdog, profile refresh and listener history into `together.js`.
- [x] Run the focused Together tests and confirm they pass.

### Task 2: Native host restoration and queue presentation

**Files:**

- Modify: `src/features/together/use-together-sync.js`
- Modify: `src/features/together/together-ui.jsx`
- Modify: `src/features/together/TogetherSidebar.jsx`
- Modify: `src/features/player/queue-panel.jsx`
- Modify: `src/app/App.jsx`
- Modify: `src/shared/i18n/locales/en.json`
- Modify: `src/shared/i18n/locales/de.json`

**Interfaces:**

- Consumes: Task 1's restore state and played-history snapshot.
- Produces: native host adoption, listener history rendering, reconnect controls and non-empty suggestion presentation.

- [x] Add failing pure tests for the host-restoration decision and listener queue composition.
- [x] Run the focused test and verify the new cases fail.
- [x] Adapt the synchronization hook to guard host reports while the native engine adopts the room state and queue.
- [x] Render connection-loss controls, listener history and suggestions without a false empty state.
- [x] Run focused Together tests and the JavaScript suite.

### Task 3: Localization and product cleanup

**Files:**

- Modify: `src/shared/i18n/locales/*.json`
- Modify: `src/features/settings/settings-panel.jsx`
- Modify: `src/features/settings/settings-sidebar.jsx`
- Modify: `src/features/settings/tabs/appearance-settings-tab.jsx`
- Modify: `src/features/settings/tabs/playback-settings-tab.jsx`
- Modify: `docs/index.html`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**

- Consumes: upstream locale values and approved product decisions.
- Produces: merged translations/credits, Toki Pona availability metadata, stable-feature labels and current documentation.

- [x] Merge upstream locale changes by key while retaining fork-only keys and validate every JSON file.
- [x] Remove Beta labels for Overlay, Crossfade and App Icon.
- [x] Remove the stale Listen Together website label and refresh README/changelog without importing Ofuda or upstream release identity.
- [x] Run locale validation, lint and build.

### Task 4: Record ancestry and verify the integration

**Files:**

- Modify: `docs/upstream-sync-2026-10-14.md`
- Modify: `.ai/STATUS.md`
- Modify: `.ai/milestones/AGENTS.md`
- Modify: `.ai/milestones/M2-upstream-alpha42-sync/**`

**Interfaces:**

- Consumes: the verified adapted tree from Tasks 1–3.
- Produces: upstream merge ancestry and final project hand-off.

- [x] Merge `upstream/master` with `--no-commit`, resolve the tree to the verified adapted implementation, and exclude protected/inapplicable upstream files.
- [x] Run JavaScript tests, Rust tests, `npm run lint`, `npm run build`, JSON validation and `git diff --check`.
- [x] Record dispositions, exact validation results and remaining platform limitations.
- [x] Commit the completed merge.
