import { useEffect, useMemo, useState } from "react";
import { usePersistedState, storageCodecs } from "@/shared/hooks/use-persisted-state.js";
import { native } from "@/shared/api/tauri.js";

export function useAccessibility() {
  const [reduceMotionPref, onReduceMotionChange] = usePersistedState(
    "kodama-reduce-motion",
    "system",
    {
      deserialize: (raw) => {
        const value = JSON.parse(raw);
        if (!["system", "on", "off"].includes(value))
          throw new TypeError("Invalid motion preference");
        return value;
      },
    }
  );
  const [monoAudio, setMonoAudio] = usePersistedState(
    "kodama-mono-audio",
    false,
    storageCodecs.boolean
  );
  const [accentContrast, setAccentContrast] = usePersistedState(
    "kodama-accent-contrast",
    false,
    storageCodecs.boolean
  );
  const [announceTracks, setAnnounceTracks] = usePersistedState(
    "kodama-announce-tracks",
    true,
    storageCodecs.boolean
  );
  const [systemReduced, setSystemReduced] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setSystemReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const reduceMotion =
    reduceMotionPref === "on" || (reduceMotionPref === "system" && systemReduced);
  useEffect(() => {
    native.setAudioMono(monoAudio).catch(() => {});
  }, [monoAudio]);
  useEffect(() => {
    document.documentElement.dataset.reduceMotion = String(reduceMotion);
    document.documentElement.dataset.accentContrast = String(accentContrast);
  }, [reduceMotion, accentContrast]);
  return useMemo(
    () => ({
      reduceMotion,
      reduceMotionPref,
      onReduceMotionChange,
      monoAudio,
      onToggleMonoAudio: () => setMonoAudio((value) => !value),
      accentContrast,
      onToggleAccentContrast: () => setAccentContrast((value) => !value),
      announceTracks,
      onToggleAnnounceTracks: () => setAnnounceTracks((value) => !value),
    }),
    [
      reduceMotion,
      reduceMotionPref,
      onReduceMotionChange,
      monoAudio,
      setMonoAudio,
      accentContrast,
      setAccentContrast,
      announceTracks,
      setAnnounceTracks,
    ]
  );
}
