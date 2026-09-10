import { parseDurationToSeconds } from "@/features/lyrics/parse.js";
import { isNativeRuntime, native } from "@/shared/api/tauri.js";

function artistNames(artists) {
  if (Array.isArray(artists)) {
    return artists.map((artist) => artist?.name || artist).filter(Boolean);
  }
  return artists ? [artists] : [];
}

export function toNativePlaybackTrack(track) {
  if (!track?.videoId) return null;
  const numericDuration =
    typeof track.durationSeconds === "number"
      ? track.durationSeconds
      : typeof track.duration === "number"
        ? track.duration
        : parseDurationToSeconds(track.duration);
  return {
    videoId: String(track.videoId),
    title: String(track.title || ""),
    artists: artistNames(track.artists),
    album: typeof track.album === "string" ? track.album : track.album?.name || "",
    thumbnail: typeof track.thumbnail === "string" ? track.thumbnail : "",
    durationSeconds: Number.isFinite(numericDuration) ? numericDuration : null,
  };
}

function transitionOverrides(overrides, queue) {
  const videoIds = new Set((queue || []).map((track) => track?.videoId).filter(Boolean));
  return Object.entries(overrides || {}).flatMap(([key, value]) => {
    const fromVideoId = [...videoIds].find((id) => key.startsWith(`${id}__`));
    if (!fromVideoId) return [];
    const toVideoId = key.slice(fromVideoId.length + 2);
    if (!videoIds.has(toVideoId)) return [];
    const seconds = Number(value?.secs);
    if (!Number.isFinite(seconds)) return [];
    return [
      {
        fromVideoId,
        toVideoId,
        seconds,
      },
    ];
  });
}

async function invokeEngine(command) {
  if (!isNativeRuntime()) return null;
  try {
    return await command();
  } catch (error) {
    console.warn("[PlaybackEngine] command failed:", error);
    return null;
  }
}

export function getNativeSnapshot() {
  return invokeEngine(native.getPlayerSnapshot);
}

export function replaceNativeQueue(queue) {
  const tracks = (queue || []).map(toNativePlaybackTrack).filter(Boolean);
  return invokeEngine(() => native.replacePlaybackQueue(tracks));
}

export function setNativeCurrentTrack(track) {
  return invokeEngine(() => native.setPlaybackCurrentTrack(toNativePlaybackTrack(track)));
}

export function updateNativeTransport({ shuffle, repeat, volume }) {
  return invokeEngine(() =>
    native.updatePlaybackTransport({
      shuffle: !!shuffle,
      repeat: repeat || "none",
      volume: Number.isFinite(volume) ? volume : undefined,
    })
  );
}

export function updateNativeTransitionPolicy({
  crossfade,
  crossfadeOverrides,
  queue,
  playbackProgressive,
  automaticCrossfade,
  mixTransitions,
  mixTransitionsEnabled,
  mixTempoLockEnabled,
}) {
  return invokeEngine(() =>
    native.updatePlaybackTransitionPolicy({
      crossfadeSeconds: Number(crossfade) || 0,
      crossfadeOverrides: transitionOverrides(crossfadeOverrides, queue),
      progressive: !!playbackProgressive,
      automaticCrossfade: !!automaticCrossfade,
      mixTransitions: Array.isArray(mixTransitions) ? mixTransitions : [],
      mixEnabled: !!mixTransitionsEnabled,
      mixTempoLock: !!mixTempoLockEnabled,
    })
  );
}

export function setNativeUiVisible(visible) {
  return invokeEngine(() => native.setPlayerUiVisible(!!visible));
}

export function setNativeLiked(liked) {
  return invokeEngine(() => native.setPlayerLiked(!!liked));
}

export function playNative() {
  return invokeEngine(native.playerPlay);
}

export function restartNative() {
  return invokeEngine(native.playerRestart);
}

export function preloadNative() {
  return invokeEngine(native.playerPreload);
}

export function pauseNative() {
  return invokeEngine(native.playerPause);
}

export function nextNative() {
  return invokeEngine(native.playerNext);
}

export function previousNative() {
  return invokeEngine(native.playerPrevious);
}

export function seekNative(position) {
  return invokeEngine(() => native.playerSeek(Math.max(0, Number(position) || 0)));
}

export function setNativeVolume(volume) {
  return invokeEngine(() => native.setPlayerVolume(Math.max(0, Math.min(1, Number(volume) || 0))));
}

export function setNativeShuffle(shuffle) {
  return invokeEngine(() => native.setPlayerShuffle(!!shuffle));
}

export function setNativeRepeat(repeat) {
  return invokeEngine(() => native.setPlayerRepeat(repeat || "none"));
}

export async function listenForNativeTrackChanges(handler) {
  try {
    const { listen } = await import("@tauri-apps/api/event");
    return await listen("playback-track-changed", ({ payload }) => handler(payload));
  } catch {
    return () => {};
  }
}

export async function listenForNativeStateChanges(handler) {
  try {
    const { listen } = await import("@tauri-apps/api/event");
    return await listen("playback-state-changed", ({ payload }) => handler(payload));
  } catch {
    return () => {};
  }
}

export async function listenForNativeProgress(handler) {
  try {
    const { listen } = await import("@tauri-apps/api/event");
    return await listen("audio-progress", ({ payload }) => handler(payload));
  } catch {
    return () => {};
  }
}
