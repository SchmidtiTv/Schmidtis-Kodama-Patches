const INSTALLED_KEY = "kodama-installed-themes";
const TOKEN_NAME = /^--[a-z0-9-]+$/;
const UNSAFE_VALUE = /[{};@]|url\s*\(|expression\s*\(/i;

export const BUILTIN_THEMES = [
  { id: "dark", label: "Dark", mode: "dark", tokens: {} },
  {
    id: "oled", label: "OLED", mode: "dark", tokens: {
      "--bg-base": "#000000", "--bg-surface": "#080808", "--bg-elevated": "#0f0f0f",
      "--bg-hover": "#141414", "--surface-1": "#0f0f0f", "--surface-2": "#181818",
      "--surface-3": "#212121", "--acrylic": "rgba(0,0,0,0.88)",
      "--stroke": "rgba(255,255,255,0.06)", "--stroke-dim": "rgba(255,255,255,0.036)",
      "--stroke-med": "rgba(255,255,255,0.11)", "--slider-track": "#282828",
    },
  },
  {
    id: "light", label: "Light", mode: "light", tokens: {
      "--bg-base": "#f0f0f0", "--bg-surface": "#ffffff", "--bg-elevated": "#e8e8e8",
      "--bg-hover": "#dcdcdc", "--surface-1": "#f7f7f7", "--surface-2": "#ededed",
      "--surface-3": "#e2e2e2", "--acrylic": "rgba(240,240,240,0.88)",
      "--stroke": "rgba(0,0,0,0.09)", "--stroke-dim": "rgba(0,0,0,0.055)",
      "--stroke-med": "rgba(0,0,0,0.15)", "--fill-subtle": "rgba(0,0,0,0.04)",
      "--fill-mod": "rgba(0,0,0,0.07)", "--fill-strong": "rgba(0,0,0,0.11)",
      "--t1": "rgba(0,0,0,0.9)", "--t2": "rgba(0,0,0,0.56)", "--t3": "rgba(0,0,0,0.38)",
      "--t4": "rgba(0,0,0,0.2)", "--slider-track": "#b8b8b8", "--status-danger": "#d32f2f",
      "--status-success": "#2e7d32", "--status-warning": "#b26a00", "--status-info": "#1565c0",
    },
  },
  {
    id: "grove", label: "Grove", mode: "dark", tokens: {
      "--bg-base": "#0e1410", "--bg-surface": "#141c17", "--bg-elevated": "#1b241e",
      "--bg-hover": "#222d25", "--surface-1": "#1b241e", "--surface-2": "#2a352d",
      "--surface-3": "#35423a", "--acrylic": "rgba(14,20,16,0.84)", "--slider-track": "#2a352d",
      "--accent": "#d8a657",
    },
  },
];

export function sanitizeTokens(tokens) {
  if (!tokens || typeof tokens !== "object") return {};
  return Object.fromEntries(
    Object.entries(tokens).filter(([name, value]) =>
      TOKEN_NAME.test(name) && typeof value === "string" && value.trim() && value.length <= 200 && !UNSAFE_VALUE.test(value)
    ).map(([name, value]) => [name, value.trim()])
  );
}

export function readInstalledThemes() {
  try {
    const stored = JSON.parse(localStorage.getItem(INSTALLED_KEY) || "[]");
    if (!Array.isArray(stored)) return [];
    return stored.filter((theme) => theme && /^[\w-]{1,64}$/.test(theme.id || "")).map((theme) => ({
      id: theme.id,
      label: typeof theme.label === "string" ? theme.label.slice(0, 40) : theme.id,
      mode: theme.mode === "light" ? "light" : "dark",
      version: typeof theme.version === "string" ? theme.version.slice(0, 24) : "",
      tokens: sanitizeTokens(theme.tokens),
    }));
  } catch {
    return [];
  }
}

export function writeInstalledThemes(themes) {
  try {
    localStorage.setItem(INSTALLED_KEY, JSON.stringify(themes.map((theme) => ({
      id: theme.id, label: theme.label, mode: theme.mode === "light" ? "light" : "dark",
      version: theme.version || "", tokens: sanitizeTokens(theme.tokens),
    }))));
    return true;
  } catch {
    return false;
  }
}

export function allThemes() {
  const installed = readInstalledThemes();
  const byId = new Map(installed.map((theme) => [theme.id, theme]));
  const builtinIds = new Set(BUILTIN_THEMES.map((theme) => theme.id));
  return [...BUILTIN_THEMES.map((theme) => byId.get(theme.id) || theme), ...installed.filter((theme) => !builtinIds.has(theme.id))];
}

export function findTheme(id) {
  return allThemes().find((theme) => theme.id === id) || BUILTIN_THEMES[0];
}

export function tokensToCss(tokens) {
  return Object.entries(tokens).map(([name, value]) => `${name}:${value}`).join(";");
}
