export const HDR_ICON_BTN =
  "w-[46px]! h-[30px]! bg-[var(--surface-2)]! hover:bg-[var(--surface-3)]! text-primary!";
export const HDR_H = 30;
export const HDR_NOTCH = 6;
export function hdrCorners(left, right, height = HDR_H) {
  const l = left ? HDR_NOTCH : height / 2;
  const r = right ? HDR_NOTCH : height / 2;
  return {
    borderTopLeftRadius: l,
    borderBottomLeftRadius: l,
    borderTopRightRadius: r,
    borderBottomRightRadius: r,
  };
}
