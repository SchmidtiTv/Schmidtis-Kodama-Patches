// HeroUI needs the dark class for custom dark themes such as OLED.
export function applyTheme(theme) {
  const value = theme || "dark";
  document.documentElement.setAttribute("data-theme", value);
  document.documentElement.classList.toggle("dark", value !== "light");
  return value;
}

export function readTheme() {
  try {
    return localStorage.getItem("kiyoshi-theme") || "dark";
  } catch {
    return "dark";
  }
}
