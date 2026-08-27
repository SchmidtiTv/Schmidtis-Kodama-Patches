export const CSS_FONT_SIZES = [10, 11, 12, 13, 14, 15, 16, 18, 20, 22];

export function readFontScale() {
  const value = Number.parseFloat(localStorage.getItem("kiyoshi-font-scale"));
  return Number.isFinite(value) ? value : 1;
}

export function applyFontScale(scale = readFontScale()) {
  CSS_FONT_SIZES.forEach((size) => {
    document.documentElement.style.setProperty(`--t${size}`, `${Math.round(size * scale)}px`);
  });
}
