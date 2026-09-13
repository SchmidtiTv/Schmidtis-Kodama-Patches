import { findTheme } from "@/shared/lib/themes.js";

function read(key, fallback = null) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function readScale(key) {
  const value = Number.parseFloat(read(key, "1"));
  return Number.isFinite(value) ? value : 1;
}

export function appearanceSnapshot() {
  const themeId = read("kiyoshi-theme", "dark");
  const theme = findTheme(themeId);
  return {
    theme: theme.label || themeId,
    highContrast: read("kiyoshi-high-contrast") === "true",
    sharpCorners: read("kiyoshi-sharp-corners") === "true",
    rtl: read("kiyoshi-rtl-layout") === "true",
    uiZoom: readScale("kiyoshi-ui-zoom"),
    fontScale: readScale("kiyoshi-font-scale"),
  };
}

export function appearanceChips(snapshot = appearanceSnapshot()) {
  const chips = [snapshot.theme];
  if (snapshot.highContrast) chips.push("high contrast");
  if (snapshot.sharpCorners) chips.push("sharp corners");
  if (snapshot.rtl) chips.push("RTL");
  if (snapshot.uiZoom !== 1) chips.push(`zoom ${Math.round(snapshot.uiZoom * 100)}%`);
  if (snapshot.fontScale !== 1) chips.push(`font ${Math.round(snapshot.fontScale * 100)}%`);
  return chips;
}
