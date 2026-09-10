import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { fetchThemeCatalogue, installTheme } from "@/shared/lib/theme-catalogue.js";
import { SettingsSectionLabel } from "@/shared/ui/settings-controls.jsx";

export function ThemeCatalogue({ onThemeChange, t }) {
  const [themes, setThemes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchThemeCatalogue().then((next) => {
      if (!active) return;
      setThemes(next.filter((theme) => !theme.builtin));
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  const install = (theme) => {
    if (installTheme(theme)) {
      setThemes((current) => current.map((entry) =>
        entry.id === theme.id ? { ...entry, installed: true } : entry
      ));
      onThemeChange(theme.id);
    }
  };

  return (
    <div style={{ marginTop: 18 }}>
      <SettingsSectionLabel>{t("themeCatalogue")}</SettingsSectionLabel>
      {loading && <div className="text-xs text-muted">{t("themeCatalogueLoading")}</div>}
      {!loading && !themes.length && (
        <div className="text-xs text-muted">{t("themeCatalogueEmpty")}</div>
      )}
      <div className="flex flex-col gap-2">
        {themes.map((theme) => (
          <div
            key={theme.id}
            className="flex items-center justify-between gap-3 rounded-xl border border-border px-3 py-2.5"
          >
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{theme.title}</div>
              {theme.description && (
                <div className="mt-0.5 text-xs text-muted truncate">{theme.description}</div>
              )}
            </div>
            <Button
              size="sm"
              variant="secondary"
              isDisabled={theme.builtin || theme.installed}
              onPress={() => install(theme)}
            >
              {theme.builtin || theme.installed ? t("themeInstalled") : t("themeInstall")}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
