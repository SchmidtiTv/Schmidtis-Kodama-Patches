// Share native playback snapshots and commands between the compact and fullscreen players.
import { useSyncExternalStore } from "react";

let _state = {
  title: "",
  artists: "",
  thumbnail: "",
  isPlaying: false,
  position: 0,
  duration: 0,
  hasTrack: false,
  shuffle: false,
  repeat: "none",
  track: null,
};
const _listeners = new Set();

export function setNowPlaying(s) {
  let changed = false;
  for (const k in s) {
    if (_state[k] !== s[k]) {
      changed = true;
      break;
    }
  }
  if (!changed) return;
  _state = s;
  _listeners.forEach((l) => l());
}
function subscribe(l) {
  _listeners.add(l);
  return () => _listeners.delete(l);
}
function getSnapshot() {
  return _state;
}
export function useNowPlaying() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

// Transport and library actions register independently, so preserve existing handlers.
let _handlers = { action: null, seek: null, play: null, enqueue: null };
export function registerPlayerCommands(h) {
  _handlers = { ..._handlers, ...h };
}

// Lyrics follow the native playback clock exposed by IpcAudio.
let _audio = null;
export function registerAudio(a) {
  _audio = a;
}
export function getAudio() {
  return _audio;
}
export function sendPlayerCommand(action) {
  _handlers.action && _handlers.action(action);
}
export function sendSeek(seconds) {
  _handlers.seek && _handlers.seek(seconds);
}
export function sendPlay(track, trackList) {
  _handlers.play && _handlers.play(track, trackList);
}
export function sendEnqueue(track, mode) {
  _handlers.enqueue && _handlers.enqueue(track, mode);
} // mode: "next" | "end"
