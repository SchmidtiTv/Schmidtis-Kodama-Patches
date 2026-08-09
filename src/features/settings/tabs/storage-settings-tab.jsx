import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, CardRoot, ToggleButton, ToggleButtonGroupRoot, cn } from "@heroui/react";

import { API } from "@/shared/api/client.js";
import { native } from "@/shared/api/tauri.js";
import {
  ArrowClockwise,
  Check,
  DownloadSimple,
  FolderOpen,
  HardDrives,
  ImageSquare,
  Microphone,
  MusicNote,
  Queue,
  Sliders,
  Trash,
  VinylRecord,
} from "@/shared/icons/icons.jsx";
import {
  SettingRow,
  SettingsSectionDesc,
  SettingsSectionLabel,
  Slider,
  Toggle,
} from "@/shared/ui/settings-controls.jsx";
import {
  EXPORT_DIRECTORY_KEY,
  EXPORT_FILENAME_PATTERN_KEY,
  REMEMBER_EXPORT_DIRECTORY_KEY,
  buildExportFilename,
  storedFilenamePattern,
} from "@/shared/lib/export-preferences.js";

const MAX_CACHE_STEPS = [100, 250, 500, 1000, 2000, 5000, 0];
const CACHE_KEYS = ["songs", "lyrics", "playlists", "albums", "images"];
const BROWSING_CACHE_KEYS = ["lyrics", "playlists", "albums", "images"];
const CACHE_PRESETS = {
  minimal: { songs: false, lyrics: true, playlists: false, albums: false, images: false },
  balanced: { songs: false, lyrics: true, playlists: true, albums: true, images: true },
  offline: { songs: true, lyrics: true, playlists: true, albums: true, images: true },
};

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function cacheLimitLabel(value, t) {
  if (value === 0) return t("unlimited");
  if (value >= 1000) return `${value / 1000} GB`;
  return `${value} MB`;
}

export function StorageSettingsTab({ t }) {
  return (
    <div>
      <SettingsSectionDesc style={{ marginTop: 0 }}>{t("storageIntro")}</SettingsSectionDesc>
      <section
        id="set-sec-storage-downloads"
        data-settings-section="storage-downloads"
        className="scroll-mt-2"
      >
        <SettingsSectionLabel>{t("storageDownloads")}</SettingsSectionLabel>
        <DownloadStorageSettings t={t} />
      </section>
      <section
        id="set-sec-storage-cache"
        data-settings-section="storage-cache"
        className="scroll-mt-2"
      >
        <SettingsSectionLabel style={{ marginTop: 28 }}>{t("storageCache")}</SettingsSectionLabel>
        <CacheSettings t={t} />
      </section>
    </div>
  );
}

function DownloadStorageSettings({ t }) {
  const [directory, setDirectory] = useState(
    () => localStorage.getItem(EXPORT_DIRECTORY_KEY) || ""
  );
  const [rememberDirectory, setRememberDirectory] = useState(
    () => localStorage.getItem(REMEMBER_EXPORT_DIRECTORY_KEY) !== "false"
  );
  const [filenamePattern, setFilenamePattern] = useState(() => storedFilenamePattern(localStorage));

  const chooseDirectory = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        directory: true,
        title: t("changePath"),
        defaultPath: directory || undefined,
      });
      if (!selected) return;
      setDirectory(selected);
      localStorage.setItem(EXPORT_DIRECTORY_KEY, selected);
    } catch {
      // The directory picker is available only in the desktop app.
    }
  };

  const resetDirectory = () => {
    setDirectory("");
    localStorage.removeItem(EXPORT_DIRECTORY_KEY);
  };

  const updateRememberDirectory = (value) => {
    setRememberDirectory(value);
    localStorage.setItem(REMEMBER_EXPORT_DIRECTORY_KEY, String(value));
  };

  const updateFilenamePattern = (value) => {
    setFilenamePattern(value);
    localStorage.setItem(EXPORT_FILENAME_PATTERN_KEY, value);
  };

  const filenamePreview = buildExportFilename(
    { title: t("exportFilenameExampleTitle"), artists: t("exportFilenameExampleArtist") },
    "mp3",
    filenamePattern
  );

  return (
    <div className="flex flex-col gap-1.5">
      <SettingRow
        label={t("defaultSavePath")}
        icon={<DownloadSimple />}
        description={directory || t("defaultSavePathDesc")}
      >
        <div className="flex gap-1.5">
          {directory && (
            <Button variant="ghost" size="sm" onPress={resetDirectory}>
              {t("resetPath")}
            </Button>
          )}
          <Button variant="primary" size="sm" onPress={chooseDirectory}>
            {t("changePath")}
          </Button>
        </div>
      </SettingRow>
      <SettingRow
        label={t("rememberExportDirectory")}
        description={t("rememberExportDirectoryDesc")}
        icon={<HardDrives />}
      >
        <Toggle
          value={rememberDirectory}
          onChange={updateRememberDirectory}
          ariaLabel={t("rememberExportDirectory")}
        />
      </SettingRow>
      <SettingRow
        label={t("exportFilename")}
        description={`${t("exportFilenameDesc")} · ${filenamePreview}`}
        icon={<MusicNote />}
      >
        <ToggleButtonGroupRoot
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={[filenamePattern]}
          onSelectionChange={(keys) => {
            const value = [...keys][0];
            if (value) updateFilenamePattern(value);
          }}
          size="sm"
        >
          <ToggleButton id="artist-title">{t("exportFilenameArtistTitle")}</ToggleButton>
          <ToggleButton id="title-artist">{t("exportFilenameTitleArtist")}</ToggleButton>
          <ToggleButton id="title">{t("exportFilenameTitleOnly")}</ToggleButton>
        </ToggleButtonGroupRoot>
      </SettingRow>
    </div>
  );
}

function CacheSettings({ t }) {
  const [stats, setStats] = useState(null);
  const [maxCacheMb, setMaxCacheMb] = useState(0);
  const [busy, setBusy] = useState({});
  const [cleared, setCleared] = useState({});
  const [fetchError, setFetchError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const categories = useMemo(
    () => [
      {
        key: "songs",
        label: t("cacheSongs"),
        icon: <MusicNote />,
        color: "var(--accent)",
        tint: "color-mix(in srgb, var(--accent) 14%, transparent)",
      },
      {
        key: "lyrics",
        label: t("cacheLyrics"),
        icon: <Microphone />,
        color: "#8b7cf6",
        tint: "rgba(139,124,246,.14)",
      },
      {
        key: "playlists",
        label: t("cachePlaylists"),
        icon: <Queue />,
        color: "#3a9fd6",
        tint: "rgba(58,159,214,.14)",
      },
      {
        key: "albums",
        label: t("cacheAlbums"),
        icon: <VinylRecord />,
        color: "#d1931d",
        tint: "rgba(209,147,29,.14)",
      },
      {
        key: "images",
        label: t("cacheImages"),
        icon: <ImageSquare />,
        color: "#36a867",
        tint: "rgba(54,168,103,.14)",
      },
    ],
    [t]
  );

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [statsResponse, settingsResponse] = await Promise.all([
        fetch(`${API}/cache/stats`),
        fetch(`${API}/cache/settings`),
      ]);
      if (!statsResponse.ok || !settingsResponse.ok) {
        throw new Error(
          `HTTP ${!statsResponse.ok ? statsResponse.status : settingsResponse.status}`
        );
      }
      const [statsData, settingsData] = await Promise.all([
        statsResponse.json(),
        settingsResponse.json(),
      ]);
      setStats(statsData);
      setMaxCacheMb(settingsData.maxCacheMb ?? 0);
      setFetchError(null);
    } catch (error) {
      setFetchError(error.message || String(error));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => load());
    return () => window.cancelAnimationFrame(frame);
  }, [load]);

  const postSettings = async (values) => {
    const response = await fetch(`${API}/cache/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  };

  const toggleCategory = async (key, value) => {
    const previous = stats?.[key]?.enabled ?? true;
    setStats((current) => current && { ...current, [key]: { ...current[key], enabled: value } });
    try {
      await postSettings({ [key]: value });
      setFetchError(null);
    } catch (error) {
      setStats(
        (current) => current && { ...current, [key]: { ...current[key], enabled: previous } }
      );
      setFetchError(error.message || String(error));
    }
  };

  const applyPreset = async (name) => {
    const values = CACHE_PRESETS[name];
    const previous = stats;
    setBusy((current) => ({ ...current, preset: true }));
    setStats(
      (current) =>
        current &&
        Object.fromEntries(
          Object.entries(current).map(([key, value]) => [
            key,
            { ...value, enabled: values[key] ?? value.enabled },
          ])
        )
    );
    try {
      await postSettings(values);
      setFetchError(null);
    } catch (error) {
      setStats(previous);
      setFetchError(error.message || String(error));
    } finally {
      setBusy((current) => ({ ...current, preset: false }));
    }
  };

  const clearCategories = async (keys, actionKey) => {
    setBusy((current) => ({ ...current, [actionKey]: true }));
    try {
      for (const category of keys) {
        const response = await fetch(`${API}/cache/clear`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ category }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
      }
      setCleared((current) => ({ ...current, [actionKey]: true }));
      window.setTimeout(() => setCleared((current) => ({ ...current, [actionKey]: false })), 1800);
      await load();
    } catch (error) {
      setFetchError(error.message || String(error));
    } finally {
      setBusy((current) => ({ ...current, [actionKey]: false }));
    }
  };

  const clearAll = () => {
    if (window.confirm(t("cacheClearAllConfirm"))) clearCategories(CACHE_KEYS, "all");
  };

  const openCacheDirectory = async () => {
    setBusy((current) => ({ ...current, openDirectory: true }));
    try {
      await native.openCacheDirectory();
    } catch (error) {
      setFetchError(error.message || String(error));
    } finally {
      setBusy((current) => ({ ...current, openDirectory: false }));
    }
  };

  const totalBytes = stats
    ? categories.reduce((sum, category) => sum + (stats[category.key]?.size ?? 0), 0)
    : 0;
  const totalItems = stats
    ? categories.reduce((sum, category) => sum + (stats[category.key]?.count ?? 0), 0)
    : 0;
  const enabledCount = stats ? CACHE_KEYS.filter((key) => stats[key]?.enabled).length : 0;
  const maxBytes = maxCacheMb * 1024 ** 2;
  const limitPercent = maxBytes ? Math.min(100, (totalBytes / maxBytes) * 100) : 0;
  const overLimit = maxBytes > 0 && totalBytes > maxBytes;
  const storedSliderIndex = MAX_CACHE_STEPS.indexOf(maxCacheMb);
  const sliderIndex = storedSliderIndex >= 0 ? storedSliderIndex : MAX_CACHE_STEPS.length - 1;
  const activePreset = stats
    ? Object.entries(CACHE_PRESETS).find(([, preset]) =>
        CACHE_KEYS.every((key) => stats[key]?.enabled === preset[key])
      )?.[0]
    : undefined;

  const updateLimit = async (index) => {
    const value = MAX_CACHE_STEPS[index];
    const previous = maxCacheMb;
    setMaxCacheMb(value);
    try {
      await postSettings({ maxCacheMb: value });
      setFetchError(null);
    } catch (error) {
      setMaxCacheMb(previous);
      setFetchError(error.message || String(error));
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      {fetchError && (
        <div className="rounded-lg bg-[var(--status-danger-soft)] px-4 py-3 text-t12 text-[var(--status-danger)]">
          {t("cacheStatsError")}: {fetchError}
        </div>
      )}

      <CardRoot
        variant="secondary"
        className="gap-0! overflow-hidden bg-surface-1 px-[18px] py-4"
        style={
          overLimit
            ? { background: "color-mix(in srgb, var(--status-danger) 8%, var(--surface-1))" }
            : undefined
        }
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-t11 font-semibold uppercase tracking-[.08em] text-muted">
              {t("cacheOverview")}
            </div>
            <div
              className={cn(
                "mt-1 text-[28px] font-bold leading-none",
                overLimit ? "text-[var(--status-danger)]" : "text-primary"
              )}
            >
              {stats ? formatBytes(totalBytes) : "…"}
            </div>
            <div className="mt-2 text-t11 text-muted">
              {stats
                ? t("cacheOverviewMeta", {
                    enabled: enabledCount,
                    total: CACHE_KEYS.length,
                    items: totalItems,
                  })
                : t("loading")}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              isDisabled={busy.openDirectory}
              onPress={openCacheDirectory}
            >
              <FolderOpen size={14} />
              {t("cacheOpenLocation")}
            </Button>
            <Button
              isIconOnly
              variant="ghost"
              size="sm"
              aria-label={t("refresh")}
              isDisabled={refreshing}
              onPress={load}
            >
              <ArrowClockwise size={15} className={refreshing ? "animate-spin" : ""} />
            </Button>
          </div>
        </div>
        <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-[var(--bg-base)]">
          {stats &&
            totalBytes > 0 &&
            categories.map((category) => {
              const percent = ((stats[category.key]?.size ?? 0) / totalBytes) * 100;
              return percent > 0 ? (
                <div
                  key={category.key}
                  style={{ width: `${percent}%`, background: category.color }}
                />
              ) : null;
            })}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
          {categories.map((category) => (
            <div key={category.key} className="flex items-center gap-1.5 text-t10 text-muted">
              <span className="h-2 w-2 rounded-full" style={{ background: category.color }} />
              {category.label}
            </div>
          ))}
        </div>
      </CardRoot>

      <SettingRow label={t("cachePreset")} description={t("cachePresetDesc")} icon={<Sliders />}>
        <ToggleButtonGroupRoot
          selectionMode="single"
          selectedKeys={activePreset ? [activePreset] : []}
          onSelectionChange={(keys) => {
            const value = [...keys][0];
            if (value) applyPreset(value);
          }}
          size="sm"
          isDisabled={busy.preset}
        >
          <ToggleButton id="minimal">{t("cachePresetMinimal")}</ToggleButton>
          <ToggleButton id="balanced">{t("cachePresetBalanced")}</ToggleButton>
          <ToggleButton id="offline">{t("cachePresetOffline")}</ToggleButton>
        </ToggleButtonGroupRoot>
      </SettingRow>

      <div className="grid grid-cols-1 gap-1.5 min-[720px]:grid-cols-2">
        {categories.map((category) => {
          const categoryStats = stats?.[category.key];
          const actionKey = `category-${category.key}`;
          return (
            <CardRoot
              key={category.key}
              variant="secondary"
              className={cn(
                "flex flex-row items-center gap-3 bg-surface-1 px-[14px] py-3 transition-opacity",
                categoryStats?.enabled === false && "opacity-55"
              )}
            >
              <div
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
                style={{ color: category.color, background: category.tint }}
              >
                {category.icon}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-t12 font-medium text-primary">{category.label}</div>
                <div className="mt-0.5 text-t10 text-muted">
                  <span style={{ color: category.color, fontWeight: 600 }}>
                    {categoryStats ? formatBytes(categoryStats.size) : "…"}
                  </span>
                  {categoryStats?.count != null && ` · ${categoryStats.count}`}
                </div>
              </div>
              <Button
                isIconOnly
                variant="ghost"
                size="sm"
                aria-label={`${t("cacheClear")} ${category.label}`}
                isDisabled={busy[actionKey] || cleared[actionKey] || !categoryStats?.count}
                onPress={() => clearCategories([category.key], actionKey)}
              >
                {cleared[actionKey] ? <Check size={12} /> : <Trash size={12} />}
              </Button>
              <Toggle
                value={categoryStats?.enabled ?? true}
                onChange={(value) => toggleCategory(category.key, value)}
                ariaLabel={`${t("cacheEnabled")} ${category.label}`}
              />
            </CardRoot>
          );
        })}
      </div>

      <CardRoot variant="secondary" className="gap-0! bg-surface-1 px-[18px] py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center text-accent">
              <HardDrives size={15} />
            </div>
            <div>
              <div className="text-t13 font-medium text-primary">{t("cacheWarningThreshold")}</div>
              <div className="mt-0.5 text-t11 text-muted">{t("cacheLimitDesc")}</div>
            </div>
          </div>
          <div
            className={cn(
              "shrink-0 text-t13 font-semibold",
              overLimit ? "text-[var(--status-danger)]" : "text-accent"
            )}
          >
            {cacheLimitLabel(maxCacheMb, t)}
          </div>
        </div>
        {maxCacheMb > 0 && (
          <div className="mt-4">
            <div className="flex justify-between text-t10 text-muted">
              <span>{t("storageUsed")}</span>
              <span>{Math.round(limitPercent)}%</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--bg-base)]">
              <div
                className={cn(
                  "h-full rounded-full",
                  overLimit ? "bg-[var(--status-danger)]" : "bg-accent"
                )}
                style={{ width: `${limitPercent}%` }}
              />
            </div>
          </div>
        )}
        <div className="mt-4">
          <Slider
            min={0}
            max={MAX_CACHE_STEPS.length - 1}
            step={1}
            value={sliderIndex}
            onChange={updateLimit}
            width="100%"
          />
          <div className="mt-2 flex justify-between text-t10 text-muted">
            <span>{cacheLimitLabel(MAX_CACHE_STEPS[0], t)}</span>
            <span>{cacheLimitLabel(MAX_CACHE_STEPS[3], t)}</span>
            <span>{cacheLimitLabel(MAX_CACHE_STEPS.at(-1), t)}</span>
          </div>
        </div>
      </CardRoot>

      <CardRoot
        variant="secondary"
        className="flex flex-row items-center justify-between gap-4 bg-surface-1 px-[18px] py-4"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center text-[var(--status-danger)]">
            <Trash size={15} />
          </div>
          <div>
            <div className="text-t13 font-medium text-primary">{t("cacheCleanup")}</div>
            <div className="mt-0.5 text-t11 text-muted">{t("cacheCleanupDesc")}</div>
          </div>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            isDisabled={busy.browsing}
            onPress={() => clearCategories(BROWSING_CACHE_KEYS, "browsing")}
          >
            {cleared.browsing ? t("cacheCleared") : t("cacheClearBrowsing")}
          </Button>
          <Button variant="danger" size="sm" isDisabled={busy.all} onPress={clearAll}>
            {cleared.all ? t("cacheCleared") : t("cacheClearAll")}
          </Button>
        </div>
      </CardRoot>
    </div>
  );
}
