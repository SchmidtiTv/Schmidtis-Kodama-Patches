# Theming

The frontend's design tokens live in [`src/app/styles/index.css`](src/app/styles/index.css) as CSS
custom properties on `:root`. Everything else — Tailwind utilities, HeroUI components, feature
CSS — resolves through those variables, so a theme switch is just swapping which values `:root`
holds.

## How a theme is selected

Three themes exist: `dark` (default), `oled`, `light`. Selection is a `data-theme` attribute on
`<html>`, toggled from `src/app/App.jsx`:

```js
const [theme, setTheme] = useState(() => localStorage.getItem("kiyoshi-theme") || "dark");
...
document.documentElement.setAttribute("data-theme", theme);
localStorage.setItem("kiyoshi-theme", theme);
```

- `dark` has no attribute selector — it *is* the base `:root` block.
- `oled` and `light` are overridden under `[data-theme="oled"]` / `[data-theme="light"]`, each
  redefining the same variable names.

A High Contrast mode layers on top of any theme via a second attribute, `data-highcontrast="true"`
(also persisted, toggled independently of `theme`). It boosts text/border contrast and, on dark
themes, drops backgrounds further toward black.

Theme + accent + high-contrast controls live in
`src/features/settings/tabs/appearance-settings-tab.jsx`; the actual attribute/property writes
happen in `App.jsx`.

## Token groups

Defined once on `:root` in `index.css`, then re-pointed per theme:

| Group | Variables | Purpose |
|---|---|---|
| Surfaces | `--bg-base`, `--bg-surface`, `--bg-elevated`, `--bg-hover`, `--surface-1/2/3` | App background → sidebar/panels → raised content → hover, plus Fluent-style elevation aliases |
| Acrylic | `--acrylic` | Translucent backdrop material |
| Stroke/Border | `--stroke`, `--stroke-dim`, `--stroke-med`, `--border` (legacy alias of `--stroke`) | Hairline borders |
| Fill states | `--fill-subtle`, `--fill-mod`, `--fill-strong` | Generic translucent fills for hover/active states |
| Text | `--t1`…`--t4` (opacity steps) aliased to `--text-primary`, `--text-secondary`, `--text-muted` | Text hierarchy |
| Accent | `--accent`, `--accent-dim` | Brand/selection colour, user-configurable (see below) |
| Radius | `--r-xs` … `--r-full`, legacy `--radius`, `--radius-lg` | Corner radius scale |
| Status | `--status-danger/success/warning` (+ `-soft`, `-line` variants) | Semantic colours, theme-tuned for contrast |
| Elevation | `--elevation-1` … `--elevation-5` | Box-shadow recipes, softer in light theme |
| Font sizes | `--t10` … `--t32` (name collision with the text-opacity `--t1`–`--t4` above is intentional legacy naming; sizes use two-digit values) | Type scale, dynamically rescaled — see below |
| Misc | `--slider-track`, `--font`, `--placeholder-gradient` | One-off tokens |

## Tailwind v4 bridge

Tailwind is configured entirely in CSS (`@tailwindcss/vite`, no `tailwind.config.js`). Two blocks
in `index.css` wire Tailwind to the tokens above:

- A plain `:root { ... }` block maps HeroUI's internal variable names (`--primary`, `--surface`,
  `--field-*`, etc.) onto the design tokens, so HeroUI components follow theme changes without
  per-component overrides. This is deliberately **unlayered** CSS — unlayered rules beat
  `@layer` rules regardless of specificity, which is required to win against HeroUI's own
  `@layer` styles.
- An `@theme inline { ... }` block maps Tailwind's generated utility tokens (`--color-surface`,
  `--color-accent`, `--font-size-t14`, …) onto the same variables, so utilities like `bg-surface`,
  `text-accent`, `text-t14` resolve live per-theme instead of being baked in at build time.

`--color-base` is intentionally *not* defined — `text-base` is Tailwind's built-in 1rem
font-size utility, and shadowing it with a color would break every HeroUI component using
`@apply text-base`. Border-radius utilities (`rounded-lg`, `rounded-2xl`, …) intentionally keep
Tailwind's default scale rather than being remapped to `--r-*`, for the same reason.

## Runtime-customizable tokens

Some tokens aren't fixed by theme — they're user preferences written directly onto
`document.documentElement.style` from `App.jsx`, layered on top of whatever the active
`data-theme` sets:

- **Accent colour** (`--accent`) — either a user-picked color persisted to `localStorage`
  (`kiyoshi-accent`), or, when "dynamic" mode is enabled, extracted live from the current track's
  cover art and reapplied on every track change.
- **Font family** (`--font`) — switches between `"MiSans Latin"` and `"OpenDyslexic"` for the
  dyslexia-friendly accessibility setting.
- **Type scale** (`--t10` … `--t22`) — recomputed on every change to the font-scale setting:
  `--t{n} = round(n * appFontScale)px` for each size in `CSS_FONT_SIZES`. `--t24`/`--t28`/`--t32`
  are defined as static px values in `index.css` and are not part of this rescale loop.

## Adding a new token

1. Add the base value to the `:root` block in `index.css` (dark theme is the default/base).
2. Override it under `[data-theme="oled"]` / `[data-theme="light"]` only if it needs to differ.
3. If it should be reachable as a Tailwind utility, add a matching entry to the `@theme inline`
   block (`--color-foo: var(--foo);` → enables `bg-foo`/`text-foo`/etc.).
4. If it needs to be more visible under accessibility mode, add an override under
   `[data-highcontrast="true"]`.
