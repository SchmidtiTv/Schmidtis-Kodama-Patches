const HIDE_DELAY_MS = 1000;
const MOVE_THRESHOLD = 3;

export function createFullscreenIdle(onVisible) {
  let timer;
  let hovered = false;
  let stopped = false;
  let lastPosition = null;

  const arm = () => {
    clearTimeout(timer);
    if (!stopped && !hovered) timer = setTimeout(() => onVisible(false), HIDE_DELAY_MS);
  };
  const reveal = () => {
    if (stopped) return;
    onVisible(true);
    arm();
  };
  arm();

  return {
    onActivity(event) {
      if (stopped) return;
      // Layout changes can synthesize mouse movement; ignore jitter, but always honor clicks.
      if (event.type === "mousemove") {
        if (
          lastPosition &&
          Math.abs(event.clientX - lastPosition.x) < MOVE_THRESHOLD &&
          Math.abs(event.clientY - lastPosition.y) < MOVE_THRESHOLD
        )
          return;
        lastPosition = { x: event.clientX, y: event.clientY };
      }
      reveal();
    },
    setHovered(value) {
      hovered = value;
      if (value) reveal();
      else arm();
    },
    stop() {
      stopped = true;
      clearTimeout(timer);
    },
  };
}
