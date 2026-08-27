/**
 * Minimal standalone entry point for the Overlay Editor window.
 * Loaded when ?overlayEditor=1 — avoids running the full App
 * (audio player, backend connections, SSE streams, etc.)
 */
import { useState, useEffect } from "react";
import { IconContext } from "@/shared/icons/icons.jsx";
import { translate } from "@/shared/i18n/i18n.js";
import { applyFontScale } from "@/shared/lib/font-scale.js";
import OverlayEditor from "@/features/overlay/OverlayEditor.jsx";
import { native } from "@/shared/api/tauri.js";

const API = "http://localhost:9847";
const EDITOR_ACCENT = "#0d99ff";
const EDITOR_ACCENT_DIM = "rgba(13, 153, 255, 0.10)";

export default function OverlayEditorApp() {
  // Strip the Windows 11 accent border from this borderless (decorations:false) window.
  useEffect(() => {
    native.removeWindowBorderFor("overlay-editor").catch(() => {});
    applyFontScale();
    document.documentElement.style.setProperty("--accent", EDITOR_ACCENT);
    document.documentElement.style.setProperty("--accent-dim", EDITOR_ACCENT_DIM);
  }, []);

  const [language] = useState(() => localStorage.getItem("kiyoshi-lang") || "de");

  const t = (key, vars) => translate(language, key, vars);

  return (
    <IconContext.Provider value={{ weight: "bold" }}>
      <div style={{ height: "100vh", background: "var(--bg-base)", overflow: "hidden" }}>
        <OverlayEditor t={t} apiBase={API} standalone />
      </div>
    </IconContext.Provider>
  );
}
