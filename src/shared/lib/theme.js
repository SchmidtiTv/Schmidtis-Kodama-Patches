import { findTheme, tokensToCss } from "./themes.js";

const THEME_STYLE_ID = "kodama-theme-vars";

export function applyTheme(theme) {
  const value = theme || "dark";
  const definition = findTheme(value);
  let style = document.getElementById(THEME_STYLE_ID);
  if (!style) {
    style = document.createElement("style");
    style.id = THEME_STYLE_ID;
    document.head.appendChild(style);
  }
  style.textContent = `:root{${tokensToCss(definition.tokens)}}`;
  document.documentElement.setAttribute("data-theme", value);
  document.documentElement.setAttribute("data-mode", definition.mode);
  document.documentElement.classList.toggle("dark", definition.mode !== "light");
  return value;
}

export function applyShape(shape) {
  document.documentElement.setAttribute("data-shape", shape || readShape());
}

export function readShape() {
  try {
    return localStorage.getItem("kiyoshi-sharp-corners") === "true" ? "sharp" : "round";
  } catch {
    return "round";
  }
}

export function readTheme() {
  try {
    return localStorage.getItem("kiyoshi-theme") || "dark";
  } catch {
    return "dark";
  }
}
