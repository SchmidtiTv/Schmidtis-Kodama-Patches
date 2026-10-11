import { installTheme, uninstallTheme } from "../../shared/lib/theme-catalogue.js";
import { fetchCatalogue } from "./catalogue.js";
import { announceStoreChange } from "./events.js";
import { installPresetEverywhere } from "./presets.js";
import { parseStoreLink } from "./web.js";

export async function installThemeEverywhere(entry) {
  const installed = installTheme(entry);
  if (installed) await announceStoreChange("themes");
  return installed;
}
export async function uninstallThemeEverywhere(id) {
  const removed = uninstallTheme(id);
  if (removed) await announceStoreChange("themes");
  return removed;
}
export async function addFromLink(value) {
  const target =
    typeof value === "string"
      ? parseStoreLink(value)
      : parseStoreLink(`kodama://store/${value?.kind}/${value?.id}`);
  if (!target) return { status: "invalid" };
  const { kind, id } = target;
  if (kind === "extensions" || kind === "widgets") return { status: "unsupported", kind, id };
  const catalogue = await fetchCatalogue();
  if (!catalogue.ok) return { status: "failed" };
  const entry = catalogue[kind]?.find((item) => item.id === id);
  if (!entry) return { status: "missing" };
  if (!entry.supported) return { status: "needsNewer", title: entry.title, min: entry.minVersion };
  if (entry.builtin || (entry.installed && !entry.updatable))
    return { status: "already", title: entry.title };
  const installed =
    kind === "themes"
      ? await installThemeEverywhere(entry)
      : await installPresetEverywhere(kind, entry);
  return {
    status: installed ? (entry.installed ? "updated" : "installed") : "failed",
    title: entry.title,
  };
}
