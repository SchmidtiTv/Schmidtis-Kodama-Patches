// Sustained-vocal presentation is gated by a line's actual timing window, then applied to its
// currently sung word. Keeping the calculation pure lets every lyrics surface share the motion.
const SUSTAIN_THRESHOLD_SECONDS = 4;
const MAX_SUSTAIN_SCALE = 1.12;

function lineEndTime(line) {
  if (Number.isFinite(line?.endTime)) return line.endTime;
  const timedWords = [...(line?.words || []), ...(line?.bgWords || [])];
  const endTimes = timedWords.map((word) => word.end).filter(Number.isFinite);
  return endTimes.length ? Math.max(...endTimes) : null;
}

export function sustainedWordScale(line, word, time) {
  if (
    !Number.isFinite(line?.time) ||
    !Number.isFinite(word?.time) ||
    !Number.isFinite(word?.end) ||
    !Number.isFinite(time)
  ) {
    return 1;
  }
  const endTime = lineEndTime(line);
  const duration = endTime == null ? 0 : endTime - line.time;
  if (duration < SUSTAIN_THRESHOLD_SECONDS) return 1;

  const wordDuration = Math.max(word.end - word.time, 0.001);
  const progress = Math.max(0, Math.min(1, (time - word.time) / wordDuration));
  // Ease out so the active word opens up early in the held vocal, then lands softly at its peak.
  const easedProgress = 1 - (1 - progress) ** 3;
  return 1 + (MAX_SUSTAIN_SCALE - 1) * easedProgress;
}
