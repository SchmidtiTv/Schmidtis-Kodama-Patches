# Upstream sync — 2026-10-11

Compared fork `main` at `a0ec8a2` with `upstream/master` at `dd41e19`, using merge-base `e0b9048dee2874a3c265a43989415469e65592f6`. Reviewed 132 upstream commits. The integration records upstream ancestry after adapting the selected behavior, following [.ai decision D-3](../.ai/DECISIONS.md#d-3-upstream-changes-are-integrated-selectively).

The user authorized comparing overlapping features and adopting the better implementation, and explicitly approved all three product changes: remove Big Picture, default to Braccato lyrics, and browse the store on the website.

## Review and disposition

| Upstream changes / source commits | Classification and comparison | Integration |
|---|---|---|
| Legal pages (`71cfdd7`, `e046d2d`, `d49fbe9`, `8b0f637`) | New functionality; website/app terms and privacy, including Together disclosure. | Bundled pages, settings legal dialog and website pages. |
| Windows lifecycle/installer (`424c030`, `c65bfb5`) | Overlap: main already owns sidecar shutdown and stale-process cleanup. Upstream adds job-object lifetime binding and update-specific runtime handling. | Added Windows job object, nonblocking shutdown/update distinction and uninstall cleanup. Retained fork listener parsing, versions, build/release configuration. |
| Braccato (`22e76c3` through `b24ce07`), duplicate translations (`a66b38f`) | Overlap: legacy lyrics/captions already exist from base and remain enhanced on main. Braccato offers upstream word rendering/stage captions; migration should not discard the existing renderer. | Braccato 1.15.3 default with Legacy selection; timing conversion, translation/romaji sizes, font, letter wave, duplicate suppression, explicit reduced-motion override. |
| Visualizers (`263bd50`, `d9c5797`, `0937e43`, `5bc45d1`, `e86ffee`) | Overlap: cover visualization/rendering already exists from base. New curve renderer and install management improve presets. | Dedicated visualizer domain, real website previews, active/remove/apply presets, linear default and circle covers. |
| Big Picture (`eec23f5`) | Product overlap; explicit user approval to remove. | Removed feature, launch paths/settings and sole navigation dependency; retained player bridge used elsewhere. |
| Overlay (`49eb5c3`–`9030621`, later `1e3aad0`, `6dc896d`, `cde63d9`, `7d96d16`, `b12c541`, `026f664`, `994370a`, `d41a4ff`, `8b7a488`) | Overlap: existing editor, schema and OBS renderer originate in base and main has modular routes/runtime. Upstream adds groups/libraries, richer paints/animations and live audio. | Adapted to existing overlay domain/service: nested groups, element folders, styles clipboard, gradients/outlines, progress interpolation, shaders, cover palette, font preview, measurement. UDP levels bridge runs FFT only for UI/OBS demand. Preserved standalone macOS controls and v1/v2 documents; fixed explicit empty paints and editor message boundary. |
| Website (`52e6567` through `8baa74a`, `dfc2b37`, `031b8d3`, `09b0783`, `1fe5c49`, `3c4263e`, `dd41e19`) | New site presentation on existing pages. | Forest/glass design, motion/spotlights, downloads, web store, invite page and fonts/media; sync script points at modular visualizer source. No deployment performed. |
| Store (`cc8c2c2`, `51ef604`, `6a304d4`) | Overlap: main already validates installed themes. Full upstream extension/widget runtime was never ported to main, so executable install semantics are not equivalent. | External browsing and strict official-catalogue deep links for themes/EQ/viz; validation, minVersion checks, installed apply/update/remove and active-state synchronization. Reused existing EQ persistence and theme contracts. Executable widgets/extensions explicitly return unsupported without fetching/executing. |
| Home/related queue (`da3c611`, `7729cf7`, `b2d3678`, `b850040`, `0ff60ea`, `859c504`, `236ba4b`, `2ac2caf`) | Overlap: main independently provides cached Home loading/retry, playlist streaming, native queue preload and shuffle. Upstream list/swipe/moods and related-song behavior are useful additions. | Retained main caching, retry, streaming and native ownership; adopted speed dial list/swipe, mood cards, radio after single selection, host queue preservation and paused-ready empty enqueue. |
| Settings cosmetics (`15124ec`–`89e9ecf`) | Overlap: fork uses its own modular settings composition and account/provider controls. | Adopted relevant group rounding/picked rows; preserved fork account/provider behavior rather than restoring monolithic settings panels. |
| Accessibility (`66f893d`, `9018f1d`) | New controls over existing animations/native audio. | System/On/Off motion preference, mono fold, contrast-adjusted accents, whole-song announcements; hooked into cover, lyrics, particles, Home and player transitions. |
| Together (`53ee89b`–`93c88c7`, excluding unrelated commits listed separately) | New room behavior overlapping native playback ownership. Upstream uses browser-driven scheduling/player state; main independently owns queue, selection, transitions and integrations in Rust. | Room worker/protocol/UI, roles, people, suggestions/votes, host handover, limits/waiting/kick/close, readiness, invites/Discord. Scheduling and drift correction moved to native engine/decoder, with listener transport/queue guards and native source loading/preload retained. |
| Session/profile rendering (`2ed2193`, `f8f7f5b`) | Main already isolates playback/settings contexts; profile polling needed stable pinned identity. | Keep room readings out of App rerenders; preserve profile object identity when polling unchanged pinned IDs. |
| Documentation/release/config | Upstream changelog and CLAUDE instructions describe its own layout/release; main has AGENTS/.ai and fork release identity. | This report, plan and handoff replace upstream development instructions. Did not import release workflows/version bumps or replace analytics. Other locale removals only deleted obsolete BP keys; unused keys outside en/de retained to avoid unrelated translation churn. |

## Preserved implementation choices

- Rust remains authoritative for playback, queues, seeking, crossfades, media controls and integration state. No upstream `src/App.jsx` or backend `server.py` architecture was restored.
- The fork's cancellable parked decoder ring and nonblocking audio callback are retained. Adopted Hermite speed correction and seek fades; avoided per-frame history allocations and handled short EOF sources.
- Native source preloading and HTTP download reuse already exist on main; room preparation uses those facilities instead of a duplicate browser player.
- Frontend additions follow app → features → shared; Flask adapters call runtime services. The top-level `composer/` was excluded throughout. The pre-existing root `AGENTS.md` edit is excluded from the merge commit.
- Removed redundant section banners, obsolete Big Picture comments/aliases and narration in adapted files. Kept comments explaining timing, compatibility and concurrency constraints.

## Validation

Final results: 64 JavaScript tests, 46 Rust tests, 177 Python tests and the production frontend build pass. All seven browser smoke suites pass across the full run and targeted reruns of the two adapted suites (14 tests total). The normal `npm run e2e:browser` command hit a pre-existing parallel server-startup race; reruns explicitly started the repository's fake-sidecar/Vite helpers before invoking the same WDIO launcher. Updated selectors follow visible Search rows and HeroUI's visible switch labels. Whitespace checks pass. Backend whole-project gates report Black76 files, Ruff3294 findings and pyrefly303 errors; no overlay type errors. Exact outcomes and limitations are also recorded in the session handoff. Focused tests cover malformed room/store inputs, listener permissions, schedules/rates, queue preservation, overlay migration/paint semantics, translation timing, reduced motion and accent contrast. Windows installer/job lifetime, live OBS capture and real two-device audio timing require platform/live verification. Worker code was added locally; no worker or website deployment was performed.

Repository frontend lint has four errors in unchanged `src/shared/i18n/i18n.js` lines79–80; the same errors reproduce from `git show HEAD:...` before the merge. Backend whole-project formatting/lint/type gates also have existing findings. The four changed Python files pass Black; new files pass Ruff, and a HEAD comparison of the existing changed modules shows no added Ruff findings (71 remain there).

## Reviewed upstream commit inventory

Every commit below was inspected within the logical groups above. Intermediate feature/fix commits are integrated at the final target behavior rather than replaying superseded intermediate code.

```text
71cfdd7 feat: terms of service and privacy policy, on the website and in the app
e046d2d docs: terms and privacy name kodama@kiyoshi.dev as the contact
424c030 feat: slim Windows update installer without node.exe; uninstall removes the runtime copy
22e76c3 feat: experiment, synced lyrics drawn by Braccato (the Better Lyrics engine)
ae9dc8c feat: Braccato stage mode for video captions; active lyric line sits lower
62901a1 feat: Braccato honours Kodama's translation and romaji sizes
bae530a fix: Braccato shows translations and romaji, floated in after the lines are built
2513039 fix: Braccato draws lyrics in Kodama's own font
5321d0c fix: Braccato lyrics get their room above again; no translation that only repeats the line
2b9bb0c feat: letter wave switch for the Braccato experiment
93e01e4 feat: Braccato is the default lyrics engine, Kodama's own view stays as Legacy
b24ce07 fix: romaji pill is centred under centred caption lines
c65bfb5 fix: no taskkill error blocking Windows shutdown; backend bound to Kodama's lifetime
263bd50 fix: store previews draw visualizer presets with the real renderer; frame gets a curve
d9c5797 feat: visualizer presets show which one is active and apply with a button
0937e43 fix: removing a store visualizer preset takes it off the list and off the screen
5bc45d1 feat: the visualizer defaults to the linear style
e86ffee feat: round cover option for the cover view, carried by visualizer presets
cc8c2c2 fix: the store window follows theme changes and leaves a removed theme
a66b38f fix: Legacy lyrics and captions hide a translation that only repeats the line
eec23f5 chore: remove Big Picture mode
49eb5c3 feat(overlay): group layers
edae6ec feat(overlay): nested groups, Shift+click selection with shared colors, Save vs Save as
2001cee feat(overlay): the layers panel follows the canvas selection
3c32bbc feat(overlay): group animations with stagger, entrance replay in the editor
8983c6f feat(overlay): delay for entrance and loop animations, on layers and groups
366e2b5 fix(overlay): entrance animations play when the widget appears and on new songs
35ff3aa feat(overlay): copy and paste properties
45c233f feat(overlay): copy and paste single inspector entries with Ctrl+C / Ctrl+V
186bdcc fix(overlay): dropdowns stay open; a picked inspector entry gets a tinted ground
7cf241b docs: CLAUDE.md describes lint before build and the Tauri stub for browser testing
5d8c96a feat(overlay): ten more entrance animations
088abc7 feat(overlay): drive-in entrances from outside the canvas, at an even speed
15b08ef feat(overlay): element library
a998af7 docs: changelog line for the element library
2ba2395 feat(overlay): floating panels in the editor's own look; My Designs as list + large preview
e5eb069 docs: changelog fix line under Fixes
4f77c06 docs: overlay entrance fix under Fixes
04212c8 fix(overlay): the picked card's ring is no longer clipped at the top of the library
2382439 feat(overlay): folders in the element library
97c9c0f feat(overlay): right-click menus, empty folders, card actions in the library footer
14070d2 feat(overlay): My Designs in the library's layout, with tags
7398f2b fix(overlay): My Designs' picked card ring is no longer clipped; scroll shadows in both lists
b9ae2ea feat(overlay): text outline; marquee glides back and forth
d51339d feat(overlay): progress bar looks and effects
f73c7b2 feat(overlay): progress moves smoothly between the backend's reports
cc60715 feat(overlay): gradient fills everywhere
b396d92 fix(overlay): text outlines and tall glyphs are no longer cut off
9285b41 fix(overlay): smooth progress, outlines as SVG, editor no longer slides up
1e513e5 fix(overlay): progress advances in fractions of a pixel
388e87c feat(overlay): experimental shader layer with 13 presets
b1544dc feat(overlay): shaders react to the music with live levels from the player
9030621 feat(overlay): colors that follow the cover
52e6567 feat(site): forest redesign with the logo as a character, store on the web
539b5e1 feat(site): new lyrics preview with Braccato, looping with a crossfade
b0fda18 feat(site): one download button for your system, joined to GitHub
58c9bf3 feat(site): motion: reveal on scroll, cheering spirits, a livelier store, page transitions
51ef604 feat(store): the shop moves to the website, the app keeps what is installed
6a304d4 feat(store): Add to Kodama installs straight from the website
1e3aad0 fix(overlay): marquee text with a gradient no longer shows up shifted and cut
a6514a5 fix(site): no page transition inside the store, no flash on page changes
2d4a4f9 feat(site): a floating scrollbar, so pages no longer shift sideways
ce511df fix(site): page changes no longer flicker
6358be4 fix(site): page change is one crossfade, no empty moment in between
8eeaebe fix(site): the first frame of a page is already the page colour
8baa74a fix(site): change pages in place, so there is no dark frame between them
da3c611 feat(player): related songs after a single song, speed dial as a list, calmer library
7729cf7 feat(home): speed dial pages slide, and a touchpad can swipe them
b2d3678 perf(home): speed dial slides without re-rendering the home view mid-slide
b850040 style(home): covers without a shadow, like the library
0ff60ea feat(home): Moods & Genres as large colour cards
859c504 style(home): mood cards glow from the corner of their name into grey
15124ec style(settings): lyrics providers and Unison identity use the settings' own rows
376bfcc style(settings): every card in the settings has the groups' rounding
b068123 style(settings): accounts as a settings group with the groups' surface and rounding
43d09c3 style(settings): a picked row shows the accent tint, no ring
89e9ecf style(settings): taller account link buttons
66f893d feat(a11y): reduce motion, mono audio, readable accent, song announcements
9018f1d fix(a11y): song announcement is read whole, once
6dc896d feat(overlay): font browser with a preview beside the list
cde63d9 feat(overlay): font kinds in a grouped menu, as in Figma, with In this design
7d96d16 fix(overlay): with a menu open, moving onto another menu opens that one
b12c541 fix(overlay): layer rows keep their notches next to the round ends
026f664 fix(overlay): cover colours work in OBS, not only in the editor
994370a fix(overlay): the cover palette loads under its own address
d41a4ff fix(overlay): scrubbing a number after clicking into its field sticks
8b7a488 feat(overlay): hold Alt to measure distances, as in Figma
53ee89b feat(together): ListenTogether prototype, room server and playback sync
79dbb74 chore(together): connect to the deployed room server by default
00b6a91 feat(together): listeners catch up by playback speed instead of jumping
26468f7 feat(together): learn the device's own speed error, jump above 300 ms
f264e57 feat(together): prepare paused, then start at a set moment
f5814ba fix(together): a room moving a little no longer restarts preparing; log why
65ace69 fix(together): a listener's own queue no longer repeats or advances in a room
67ffbe8 fix(together): calmer speed control, and a reconnect replaces its old socket
c27f839 fix(together): wait out a whole load, and do not chase the room past a song's end
2cf0c2d feat(together): the host shares what plays next; listeners warm it up
d404a8a fix(together): the room moves at the host's real speed
c76da35 chore(together): log player stalls and room jumps in the debug view
f4d559e chore(together): scrollable, copyable sync log
2173fbd fix(together): log join used a raw line break in a string
f8f7f5b perf(together): App no longer re-renders with every sync reading
2ed2193 perf: the minute's session check no longer re-renders the whole app
e41f70d feat(together): positions carry the player's own reading time
d811ef8 feat(together): pill in the player bar, Room tab, room settings
5c2e4fe fix(together): a member's song crashed the host's queue panel
53346fd feat(together): the room lives in the sidebar, as a card above the profile
7d43411 style(together): room card buttons and text at the sidebar's own size
e55b2f0 feat(together): profile pictures (opt-in), who added a song, taking songs back out
e213149 feat(together): profile pictures shown by default
c47d3a7 feat(together): the host can name the room
8a36266 feat(together): a listener can't start their own music in a room
1f3f5d2 feat(together): invite page at /together/ and a room lookup for it
5e039ac style(together): invite code in the page's own font, no hint line
d49fbe9 docs(privacy): Listen together
8b0f637 docs(privacy): the invite page's cover comes from YouTube, which sees the IP
d0971ff feat(together): 'Listen along' button on the Discord status
cb7f8aa feat(together): the Room tab replaces the Queue tab, queue first
58baef9 fix(together): say who added a song in the row, not as a badge on the cover
d1d5e6e fix(together): listener's room list in the queue's own rows; no stray 0
236ba4b fix(together): a host's single song plays now and keeps the room's queue
688cfe0 feat(together): roles, member limit, waiting room, kick, hand-over, close (server)
38d91dd feat(together): roles, People tab, waiting room, limit, host hand-over (app)
4512092 fix(together): room limit as the app's dropdown, not a native select
dfc2b37 feat(site): feature spotlights with animated scenes
031b8d3 feat(site): first screen with the features heading, spirit reactions
09b0783 feat(site): forest, wider landing, clickable spirit, mobile menu
93c88c7 feat(together): song suggestions with votes
2ac2caf fix(queue): a song queued into an empty player stands ready instead of starting
1fe5c49 feat(site): "Coming soon!" on Listen together until the release
3c4263e fix(site): overlay scene clicks the shader preset it selects
dd41e19 feat(site): liquid glass buttons, header button group, glass heading
```
