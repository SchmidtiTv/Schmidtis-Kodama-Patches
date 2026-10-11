/** Related songs extend the selected seed without replacing songs explicitly queued meanwhile. */
export function appendRelatedTracks(queue, related) {
  const seen = new Set(queue.map((track) => track.videoId));
  const additions = (Array.isArray(related) ? related : []).filter((track) => {
    if (!track?.videoId || seen.has(track.videoId)) return false;
    seen.add(track.videoId);
    return true;
  });
  return [...queue, ...additions];
}

export function roomQueueForSelection(track, queue, currentId) {
  const current = queue.findIndex((item) => item.videoId === currentId);
  return [track, ...queue.slice(current + 1).filter((item) => item.videoId !== track.videoId)];
}
