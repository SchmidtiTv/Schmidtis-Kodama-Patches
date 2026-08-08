/**
 * Moves the active track to the front and randomizes every upcoming track.
 * Keeping the active track fixed lets the queue remain an accurate playback
 * plan while shuffle is enabled.
 */
export function shuffleQueueAfterCurrent(queue, currentVideoId) {
  const currentIndex = queue.findIndex((track) => track.videoId === currentVideoId);
  if (currentIndex < 0) return [...queue];

  const upcoming = queue.filter((_, index) => index !== currentIndex);
  for (let index = upcoming.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [upcoming[index], upcoming[swapIndex]] = [upcoming[swapIndex], upcoming[index]];
  }
  return [queue[currentIndex], ...upcoming];
}
