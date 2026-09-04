import { useEffect } from "react";
import { native } from "@/shared/api/tauri.js";

/**
 * Synchronizes playback-integration preferences with the native engine.
 * Settings arrive through a ref because App declares the integration settings
 * after it creates the controller. App increments integrationRevision whenever
 * one changes so the Rust worker applies it immediately.
 */
export function usePlayerNativeBridges({ integrationsRef, integrationRevision }) {
  useEffect(() => {
    const settings = integrationsRef.current;
    native
      .updatePlayerIntegrations({
        discordEnabled: !!settings.discordRpc,
        discordStatusDisplay: settings.discordStatusDisplay || "song",
        hideDiscordWhilePaused: settings.hideDiscordWhilePaused !== false,
        lastfmConnected: !!settings.lastfmConnected,
        youtubeHistoryEnabled: !!settings.youtubeHistoryEnabled,
        overlayUpdatesEnabled: true,
        remoteEnabled: !!settings.remoteEnabled,
      })
      .catch(() => {
        // Browser E2E and the HTML-audio fallback do not expose native integrations.
      });
  }, [integrationsRef, integrationRevision]);
}
