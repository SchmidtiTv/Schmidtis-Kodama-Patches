const versionPattern = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/;
export function compareCatalogueVersions(left, right) {
  const a = versionPattern.exec(String(left || ""));
  const b = versionPattern.exec(String(right || ""));
  if (!a || !b) return null;
  for (let index = 1; index <= 3; index++) {
    if (+a[index] !== +b[index]) return +a[index] < +b[index] ? -1 : 1;
  }
  if (a[4] === b[4]) return 0;
  if (!a[4]) return 1;
  if (!b[4]) return -1;
  const x = a[4].split(".");
  const y = b[4].split(".");
  for (let index = 0; index < Math.max(x.length, y.length); index++) {
    if (x[index] === y[index]) continue;
    if (x[index] === undefined) return -1;
    if (y[index] === undefined) return 1;
    const numericX = /^\d+$/.test(x[index]);
    const numericY = /^\d+$/.test(y[index]);
    if (numericX && numericY) return +x[index] < +y[index] ? -1 : 1;
    if (numericX !== numericY) return numericX ? -1 : 1;
    return x[index] < y[index] ? -1 : 1;
  }
  return 0;
}

export function supportsCatalogueEntry(
  entry,
  appVersion = typeof __APP_VERSION__ === "undefined" ? "0.0.0" : __APP_VERSION__
) {
  if (!entry?.minVersion) return true;
  const comparison = compareCatalogueVersions(appVersion, entry.minVersion);
  return comparison !== null && comparison >= 0;
}
