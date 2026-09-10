import { useEffect, useRef, useState } from "react";
import { VIZ_DEFAULTS } from "@/features/player/player-ui.jsx";
export function useVisualizerSettingsTab({ t, uiZoom, vizConfig, onUpdateViz }) {
  // Visualizer preview scales with the window height (live on resize) so on short windows it
  // shrinks — both the box AND the cover — leaving room to reach the options below.
  const [winH, setWinH] = useState(() => window.innerHeight);
  const [winW, setWinW] = useState(() => window.innerWidth);
  useEffect(() => {
    const onResize = () => {
      setWinH(window.innerHeight);
      setWinW(window.innerWidth);
    };
    const observer = new ResizeObserver(onResize);
    observer.observe(document.documentElement);
    onResize();
    return () => observer.disconnect();
  }, []);
  const vizPreviewH = Math.round(Math.max(260, Math.min(620, winH * 0.48)));
  const vizCoverSize = Math.round(Math.max(130, Math.min(260, vizPreviewH * 0.42)));
  const [vizPreviewOpen, setVizPreviewOpen] = useState(
    () => localStorage.getItem("kodama-viz-preview") !== "collapsed"
  );
  const toggleVizPreview = () =>
    setVizPreviewOpen((o) => {
      const n = !o;
      localStorage.setItem("kodama-viz-preview", n ? "open" : "collapsed");
      return n;
    });
  // Scaled-replica preview: render at the same proportions as the fullscreen cover view (coverSize
  // 260, window-sized container) but shrunk by s = previewWidth / windowWidth. Scaling the pixel
  // config values (barLength/gap/thickness) along with the cover + container makes the preview a
  // true 1:1 miniature of the real visualizer, including the linear bar spread.
  const vizPreviewRef = useRef(null);
  const [vizPreviewW, setVizPreviewW] = useState(0);
  useEffect(() => {
    const el = vizPreviewRef.current;
    if (!el || !vizPreviewOpen) return;
    const ro = new ResizeObserver(() => setVizPreviewW(el.clientWidth));
    ro.observe(el);
    setVizPreviewW(el.clientWidth);
    return () => ro.disconnect();
  }, [vizPreviewOpen]);
  const vizWinW = winW / (uiZoom || 1);
  const vizScale = vizPreviewW > 0 && vizWinW > 0 ? vizPreviewW / vizWinW : vizCoverSize / 260;
  const vizPreviewHReplica =
    vizPreviewW > 0 && vizWinW > 0 ? Math.round((vizPreviewW * winH) / winW) : vizPreviewH;
  const vizPreviewCover = Math.max(60, Math.round(260 * vizScale));

  // Visualizer presets — save/apply/import/export named snapshots of the config (same pattern as
  // the Overlay Editor's design profiles). Stored locally as { id, name, savedAt, config }.
  const [vizPresets, setVizPresets] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("kodama-visualizer-presets") || "[]");
    } catch {
      return [];
    }
  });
  const persistVizPresets = (next) => {
    setVizPresets(next);
    try {
      localStorage.setItem("kodama-visualizer-presets", JSON.stringify(next));
    } catch {
      /* intentionally ignored */
    }
  };
  const [vizPresetName, setVizPresetName] = useState("");
  const vizImportRef = useRef(null);
  const saveVizPreset = () => {
    const name = vizPresetName.trim() || t("preset") || "Preset";
    persistVizPresets([
      {
        id: crypto.randomUUID(),
        name,
        savedAt: new Date().toISOString(),
        config: {
          ...vizConfig,
        },
      },
      ...vizPresets,
    ]);
    setVizPresetName("");
  };
  const applyVizPreset = (p) =>
    onUpdateViz({
      ...VIZ_DEFAULTS,
      ...p.config,
    });
  const overwriteVizPreset = (id) =>
    persistVizPresets(
      vizPresets.map((preset) =>
        preset.id === id
          ? { ...preset, savedAt: new Date().toISOString(), config: { ...vizConfig } }
          : preset
      )
    );
  const deleteVizPreset = (id) => persistVizPresets(vizPresets.filter((p) => p.id !== id));
  const exportVizPreset = async (preset) => {
    const base = (preset.name || "visualizer").replace(/[^\w\s-]/g, "").trim() || "visualizer";
    const { save } = await import("@tauri-apps/plugin-dialog");
    const { writeTextFile } = await import("@tauri-apps/plugin-fs");
    const path = await save({
      defaultPath: `${base}.kodama-visualizer.json`,
      filters: [{ name: "Visualizer preset", extensions: ["json"] }],
    });
    if (!path) return;
    await writeTextFile(
      path,
      JSON.stringify({ name: preset.name, savedAt: preset.savedAt, config: preset.config }, null, 2)
    );
  };
  const handleVizImport = (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    Promise.all(files.map((f) => f.text())).then((texts) => {
      const imported = [];
      for (const text of texts) {
        try {
          const parsed = JSON.parse(text);
          const items = Array.isArray(parsed) ? parsed : [parsed];
          for (const item of items) {
            const cfg = item && (item.config || item);
            if (
              cfg &&
              typeof cfg === "object" &&
              ("shape" in cfg || "barCount" in cfg || "barLength" in cfg)
            ) {
              imported.push({
                id: crypto.randomUUID(),
                name: item.name || t("preset") || "Preset",
                savedAt: new Date().toISOString(),
                config: cfg,
              });
            }
          }
        } catch {
          /* skip malformed files */
        }
      }
      if (imported.length > 0) persistVizPresets([...imported, ...vizPresets]);
    });
  };
  return {
    winH,
    setWinH,
    winW,
    setWinW,
    vizPreviewH,
    vizCoverSize,
    vizPreviewOpen,
    setVizPreviewOpen,
    toggleVizPreview,
    vizPreviewRef,
    vizPreviewW,
    setVizPreviewW,
    vizScale,
    vizPreviewHReplica,
    vizPreviewCover,
    vizPresets,
    setVizPresets,
    persistVizPresets,
    vizPresetName,
    setVizPresetName,
    vizImportRef,
    saveVizPreset,
    applyVizPreset,
    overwriteVizPreset,
    deleteVizPreset,
    exportVizPreset,
    handleVizImport,
  };
}
