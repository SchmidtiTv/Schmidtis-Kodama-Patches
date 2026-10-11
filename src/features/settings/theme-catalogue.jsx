import { compareCatalogueVersions } from "@/shared/lib/catalogue-version.js";
import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { fetchThemeCatalogue } from "@/shared/lib/theme-catalogue.js";
import { readInstalledThemes } from "@/shared/lib/themes.js";
import {
  addFromLink,
  onStoreChanged,
  openStoreWeb,
  uninstallThemeEverywhere,
} from "@/features/store";
import { SettingsSectionLabel } from "@/shared/ui/settings-controls.jsx";
import { useAppearanceSettings } from "./settings-context.jsx";

export function ThemeCatalogue({ onThemeChange, t }) {
  const { theme: activeTheme } = useAppearanceSettings();
  const [themes, setThemes] = useState(readInstalledThemes);
  const [catalogue, setCatalogue] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    fetchThemeCatalogue().then((next) => {
      if (alive) setCatalogue(next);
    });
    const stop = onStoreChanged((kind) => {
      if (kind === "themes") setThemes(readInstalledThemes());
    });
    return () => {
      alive = false;
      stop();
    };
  }, []);
  const remove = async (id) => {
    if (await uninstallThemeEverywhere(id)) {
      if (activeTheme === id) onThemeChange("dark");
      setThemes(readInstalledThemes());
    } else setError(t("themeStoreFailed"));
  };
  const update = async (id) => {
    const result = await addFromLink({ kind: "themes", id });
    if (result.status === "updated" || result.status === "installed")
      setThemes(readInstalledThemes());
    else if (result.status !== "already") setError(t("themeStoreFailed"));
  };
  return (
    <div style={{ marginTop: 18 }}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <SettingsSectionLabel>{t("storeLibrary")}</SettingsSectionLabel>
        <Button
          size="sm"
          variant="secondary"
          onPress={() => openStoreWeb("themes").catch(() => setError(t("themeStoreFailed")))}
        >
          {t("storeGetMore")}
        </Button>
      </div>
      {error && (
        <div className="text-xs text-danger" role="status">
          {error}
        </div>
      )}
      <div className="flex flex-col gap-2">
        {themes.map((theme) => {
          const published = catalogue.find((entry) => entry.id === theme.id);
          return (
            <div
              key={theme.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-border px-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{theme.label}</div>
                <div className="text-xs text-muted">{theme.version}</div>
              </div>
              <div className="flex gap-1.5">
                {published &&
                  compareCatalogueVersions(published.version, theme.version) > 0 &&
                  published.supported && (
                    <Button size="sm" variant="secondary" onPress={() => update(theme.id)}>
                      {t("themeUpdate")}
                    </Button>
                  )}
                <Button size="sm" variant="secondary" onPress={() => onThemeChange(theme.id)}>
                  {t("storeApply")}
                </Button>
                <Button size="sm" variant="ghost" onPress={() => remove(theme.id)}>
                  {t("themeRemove")}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
