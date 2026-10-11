/** A room clock advances only from its announced start, including scheduled starts. */
export function roomPositionAt(state, serverTime) {
  if (!state) return 0;
  return (
    state.pos +
    (state.playing ? ((state.rate || 1) * Math.max(0, serverTime - state.at)) / 1000 : 0)
  );
}

export function clockSample(samples, message, now) {
  if (!Number.isFinite(message.c) || !Number.isFinite(message.s) || message.c > now) return null;
  const rtt = now - message.c;
  const recent = [...samples, { rtt, offset: message.s - (message.c + rtt / 2), at: now }]
    .filter((sample) => now - sample.at < 30000)
    .slice(-8);
  const best = recent.reduce((a, b) => (b.rtt < a.rtt ? b : a));
  return { samples: recent, offset: best.offset, rtt: best.rtt };
}

export function validRoomMessage(message) {
  if (!message || typeof message !== "object" || typeof message.t !== "string") return false;
  if (["state", "welcome"].includes(message.t)) {
    const state = message.t === "state" ? message : message.state;
    if (
      !state ||
      !Number.isFinite(state.pos) ||
      state.pos < 0 ||
      !Number.isFinite(state.at) ||
      typeof state.playing !== "boolean" ||
      (state.rate != null &&
        (!Number.isFinite(state.rate) || state.rate < 0.98 || state.rate > 1.02))
    )
      return false;
    if (
      state.track &&
      (typeof state.track.videoId !== "string" || !/^[a-zA-Z0-9_-]+$/.test(state.track.videoId))
    )
      return false;
  }
  if (["members", "queue", "suggestions"].includes(message.t) && !Array.isArray(message.list))
    return false;
  return true;
}

export function roomRole(snapshot) {
  return snapshot.isHost ? "host" : snapshot.you?.role || "listener";
}
