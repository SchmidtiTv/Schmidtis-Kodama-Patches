# Upstream sync — 2026-10-14

Compared fork `main` at `48b9894` with `upstream/master` at `95162bb`, using merge-base `dd41e19`. Reviewed 63 upstream commits and 28 changed files outside the protected `composer/` tree.

The user approved the recommended integration: adapt all Together recovery improvements to native playback, merge localization updates and credits, mark incomplete Toki Pona as coming soon, remove stable-feature Beta labels, remove the website's stale Listen Together notice, keep the built-in overlay editor without Ofuda migration messaging, and preserve fork release identity.

## Review and disposition

| Upstream changes                                                          | Classification                             | Disposition                                                                                                   |
| ------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Together recovery (`7c4b3f2`, `01f24b1`, `547055a`, `d36f275`, `565b5d5`) | Overlapping functionality                  | Adapt into the Together feature and native synchronization boundary.                                          |
| OS media duration (`cbc3b42`)                                             | Already handled                            | Native track metadata and load-time transport updates already provide duration without the legacy App effect. |
| Locale translations and language metadata                                 | New functionality with one product overlap | Merge key-by-key, preserve fork keys, add credits/languages, and mark Toki Pona coming soon as approved.      |
| Ofuda migration (`866675c`, `f0c8a49`, part of `d5dc3dc`)                 | Overlapping product direction              | Skip; the fork retains its built-in overlay editor.                                                           |
| Stable-feature labels (`d5dc3dc`, `53be3b9`, `3f46d0d`)                   | Overlapping product labeling               | Remove Beta labels as approved.                                                                               |
| Website Listen Together release (`95162bb`)                               | Already applicable                         | Remove the stale Coming soon label.                                                                           |
| README/changelog refresh                                                  | Cleanup                                    | Adapt current features while preserving fork documentation and Composer reference.                            |
| Alpha.42 release/configuration (`560021a`, `3703cf0`, `eddef74`)          | Inapplicable                               | Preserve fork version, updater manifest and release configuration.                                            |

## Validation

Pending implementation.
