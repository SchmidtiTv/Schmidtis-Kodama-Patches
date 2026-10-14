export const ROOM_MEMORY_MAX_AGE = 24 * 60 * 60 * 1000;
export const ROOM_SILENCE_LIMIT = 15_000;

const ROOM_CODE = /^[a-z0-9]{4,16}$/i;

export function parseRememberedRoom(raw, now = Date.now(), maxAge = ROOM_MEMORY_MAX_AGE) {
  let value;
  try {
    value = JSON.parse(raw || "null");
  } catch {
    return null;
  }
  if (
    !ROOM_CODE.test(value?.room || "") ||
    !Number.isFinite(value?.at) ||
    now - value.at > maxAge
  ) {
    return null;
  }
  return {
    room: value.room.toLowerCase(),
    name: String(value.name || "").trim(),
  };
}

export function connectionIsSilent(lastHeard, now = Date.now(), limit = ROOM_SILENCE_LIMIT) {
  return lastHeard > 0 && now - lastHeard > limit;
}

export function nextPlayedTracks(played, previousTrack, nextTrack, limit = 50) {
  if (
    !previousTrack?.videoId ||
    !nextTrack?.videoId ||
    previousTrack.videoId === nextTrack.videoId ||
    played.at(-1)?.videoId === previousTrack.videoId
  ) {
    return played;
  }
  return [...played, previousTrack].slice(-limit);
}

export function hostRoomRestorePlan(room) {
  if (!room?.restoring || !room.isHost || !room.state?.track?.videoId) return null;
  return {
    state: room.state,
    queue: [
      room.state.track,
      ...(room.queue || []).filter((track) => track.videoId !== room.state.track.videoId),
    ],
  };
}

export function buildListenerRoomQueue(played, localTrack, roomTrack, upNext) {
  const current =
    localTrack?.videoId && localTrack.videoId === roomTrack?.videoId ? localTrack : roomTrack;
  return [...(played || []), current, ...(upNext || [])].filter(Boolean);
}
