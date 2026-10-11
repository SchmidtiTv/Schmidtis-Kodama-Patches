import { VIZ_DEFAULTS } from "@/features/visualizer/index.js";
import { cleanVisualizerConfig } from "@/features/visualizer/config.js";
import { useEffect, useState } from "react";
import {
  addFromLink,
  onStoreChanged,
  parseStoreLink,
  VIZ_CONFIG_KEY,
} from "@/features/store/index.js";
import { BUILTIN_THEMES, readInstalledThemes } from "@/shared/lib/themes.js";
import { loadEqualizerState } from "@/features/player/equalizer.js";
import { native } from "@/shared/api/tauri.js";
import { translate } from "@/shared/i18n/i18n.js";

export function useStoreLinks({ setVizConfig, setTheme, addToast }) {
  const [installedThemesRevision, setInstalledThemesRevision] = useState(0);
  useEffect(
    () =>
      onStoreChanged((kind) => {
        if (kind === "themes") {
          const selected = localStorage.getItem("kiyoshi-theme") || "dark";
          const exists = [...BUILTIN_THEMES, ...readInstalledThemes()].some(
            (theme) => theme.id === selected
          );
          setTheme(exists ? selected : "dark");
          setInstalledThemesRevision((revision) => revision + 1);
        } else if (kind === "visualizer") {
          try {
            setVizConfig({
              ...VIZ_DEFAULTS,
              ...cleanVisualizerConfig(JSON.parse(localStorage.getItem(VIZ_CONFIG_KEY) || "{}")),
            });
          } catch {
            /* Keep the active configuration when storage is invalid. */
          }
        } else if (kind === "equalizer") {
          const config = loadEqualizerState();
          native.setAudioEqualizer(config.enabled, config.preampDb, config.gainsDb).catch(() => {});
        }
      }),
    [setVizConfig, setTheme]
  );

  useEffect(() => {
    let disposed = false;
    let stop = () => {};
    const handle = async (url) => {
      const link = parseStoreLink(url);
      if (!link) return;
      const result = await addFromLink(link).catch(() => ({ status: "failed" }));
      if (disposed) return;
      const keys = {
        installed: "storeLinkAdded",
        updated: "storeLinkUpdated",
        already: "storeLinkAlready",
        needsNewer: "storeLinkNeedsNewer",
        missing: "storeLinkMissingShort",
        failed: "storeLinkFailed",
        unsupported: "storeLinkUnsupported",
      };
      const key = keys[result.status];
      if (key)
        addToast(
          translate(localStorage.getItem("kiyoshi-lang") || "en", key, {
            title: result.title || "",
            min: result.min || "",
          }),
          ["installed", "updated"].includes(result.status)
            ? "success"
            : result.status === "already"
              ? "info"
              : "error"
        );
    };
    import("@tauri-apps/plugin-deep-link")
      .then(async ({ getCurrent, onOpenUrl }) => {
        const urls = await getCurrent();
        if (disposed) return;
        urls?.forEach(handle);
        const cleanup = await onOpenUrl((urls) => urls.forEach(handle));
        if (disposed) cleanup();
        else stop = cleanup;
      })
      .catch(() => {});
    return () => {
      disposed = true;
      stop();
    };
  }, [addToast]);
  return installedThemesRevision;
}
