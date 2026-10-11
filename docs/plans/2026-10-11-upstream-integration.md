# Upstream integration: 2026-10-11

Goal: integrate upstream/master dd41e19 into main a0ec8a2, comparing against merge-base e0b9048. There are 132 upstream commits.

The user approved removing Big Picture, making Braccato the default, and website store browsing. Preserve native Rust playback, modular frontend/backend, fork release configuration and analytics. Exclude composer/. Preserve the existing user edit to root AGENTS.md.

- [x] Overlay: adapt groups, libraries, gradients, animations, clipboard, cover colors, font browser, measurements, shader/audio levels and OBS rendering to existing owning modules. Test schema/group/clipboard behavior and renderer boundaries.
- [x] Lyrics/Home/accessibility: Braccato and caption support, duplicate translation suppression, speed dial list/swiping, mood cards, circle covers, reduced motion, mono, contrast, announcements. Preserve cached Home loading and image retries. Test translations and data transformations.
- [x] Together: room protocol/UI, roles, voting, host handover, scheduled native playback/rate correction, queue readiness and invite links. Rust remains authoritative. Test clock math, role constraints and native state transitions.
- [x] App/native/store/site: remove Big Picture, wire settings and features, port website browsing/data installs, legal pages, shutdown job lifecycle and shared UI dependencies. Preserve runtime validation and release identity.
- [x] Review combined diff, run focused JS/Python/Rust tests then npm lint/build and backend gates. Record limitations. Record upstream ancestry only after adaptations, without including the user's AGENTS.md edit.

Review focus: malformed room/store inputs; leave/reconnect resets playback rate; listener cannot advance local queue; existing overlay documents retain appearance; reduced motion and lyric sizing apply to both captions and full lyrics.

Tradeoffs: upstream decoder resampling is useful for Together, but retain our cancellable parked ring rather than its polling; preload is already implemented on main and must be reused. Base store code was not previously ported: adapt content installation to existing validated themes rather than blindly restoring upstream extension/runtime architecture.

Review and disposition: [upstream sync report](../upstream-sync-2026-10-11.md).
