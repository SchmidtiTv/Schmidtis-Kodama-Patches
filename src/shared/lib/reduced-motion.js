export function isMotionReduced(
  browserWindow = globalThis.window,
  root = globalThis.document?.documentElement
) {
  const preference = root?.dataset?.reduceMotion;
  if (preference === "true" || preference === "false") return preference === "true";
  return !!browserWindow?.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
}
