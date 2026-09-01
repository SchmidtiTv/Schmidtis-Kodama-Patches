import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Button,
  CardRoot,
  cn,
  InputRoot,
  ProgressBar,
  ProgressBarFill,
  ProgressBarTrack,
  Spinner,
  TextFieldRoot,
} from "@heroui/react";

import {
  ArrowClockwise,
  ArrowSquareOut,
  Bug,
  CaretDown,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  GripLines,
  UserCircle,
  WarningCircle,
  X,
} from "@/shared/icons/icons.jsx";
import { API } from "@/shared/api/client.js";
import { useLang } from "@/shared/i18n/context.jsx";
import {
  generateIdentity,
  importIdentityFile,
  exportIdentityFile,
} from "@/features/lyrics/community/identity.js";
import { providerSyncLevels } from "@/features/lyrics/providers.js";
import {
  unisonSetNickname,
  unisonResetNickname,
  unisonFetchDisplayName,
} from "@/features/lyrics/community/api.js";
import {
  Toggle,
  SettingRow,
  SettingsSectionLabel,
  SettingsSectionDesc,
} from "@/shared/ui/settings-controls.jsx";
import { frontendLogs } from "./debug-log-store.js";

export const APP_VERSION = __APP_VERSION__;

export function fmtDuration(totalSec) {
  const s = Math.max(0, Math.floor(totalSec || 0));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${s}s`;
}

export function LyricsProviderList({ providers, onChange }) {
  const [dragOver, setDragOver] = useState(null);
  const isDragging = useRef(false);
  const dragOverRef = useRef(null);
  const listRef = useRef(null);

  const handlePointerDown = (e, fromIdx) => {
    e.preventDefault();
    isDragging.current = false;
    dragOverRef.current = null;
    const startY = e.clientY;

    const onMove = (me) => {
      if (Math.abs(me.clientY - startY) > 4) isDragging.current = true;
      if (!isDragging.current || !listRef.current) return;
      const rows = listRef.current.querySelectorAll("[data-provider-idx]");
      let closest = null,
        closestDist = Infinity;
      rows.forEach((row) => {
        const rect = row.getBoundingClientRect();
        const mid = rect.top + rect.height / 2;
        const dist = Math.abs(me.clientY - mid);
        if (dist < closestDist) {
          closestDist = dist;
          closest = row;
        }
      });
      if (closest) {
        const idx = parseInt(closest.dataset.providerIdx);
        dragOverRef.current = idx;
        setDragOver(idx);
      }
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      const target = dragOverRef.current;
      if (isDragging.current && target !== null && target !== fromIdx) {
        const next = [...providers];
        const [moved] = next.splice(fromIdx, 1);
        next.splice(target, 0, moved);
        onChange(next);
      }
      isDragging.current = false;
      dragOverRef.current = null;
      setDragOver(null);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  return (
    <div ref={listRef} className="flex flex-col gap-1.5">
      {providers.map((p, i) => (
        <CardRoot
          key={p.id}
          variant="secondary"
          data-provider-idx={i}
          className={cn(
            "bg-surface-1 flex flex-row items-center gap-2.5 px-[18px] py-4 border-2 transition-colors",
            dragOver === i ? "border-accent" : "border-transparent"
          )}
        >
          {/* Drag handle */}
          <div
            onPointerDown={(e) => handlePointerDown(e, i)}
            className="cursor-grab text-muted flex items-center shrink-0 touch-none"
          >
            <GripLines size={16} style={{ pointerEvents: "none" }} />
          </div>
          {/* Label */}
          <span className={cn("text-t13", p.enabled ? "text-primary" : "text-muted")}>
            {p.label}
          </span>
          {/* Sync-type tag */}
          {providerSyncLevels(p.id).map((sync) => (
                <span
                  key={sync.label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: "var(--t10)",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                    padding: "2px 6px",
                    borderRadius: "var(--r-sm)",
                    background: p.enabled ? sync.bg : "rgba(255,255,255,0.05)",
                    color: p.enabled ? sync.color : "var(--text-muted)",
                    transition: "all 0.2s",
                  }}
                >
                  {sync.icon && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 16,
                        height: 16,
                        flexShrink: 0,
                        alignSelf: "center",
                        backgroundColor: "currentColor",
                        maskImage: `url(${sync.icon})`,
                        WebkitMaskImage: `url(${sync.icon})`,
                        maskSize: "contain",
                        WebkitMaskSize: "contain",
                        maskRepeat: "no-repeat",
                        WebkitMaskRepeat: "no-repeat",
                        maskPosition: "center",
                        WebkitMaskPosition: "center",
                      }}
                    />
                  )}
                  {sync.label}
                </span>
          ))}
          <div className="flex-1" />
          {/* Enable toggle */}
          <Toggle
            value={p.enabled}
            onChange={(v) =>
              onChange(providers.map((x, j) => (j === i ? { ...x, enabled: v } : x)))
            }
          />
        </CardRoot>
      ))}
    </div>
  );
}

const _debugLevelColor = (level) => {
  if (level === "ERROR") return "#ff6b6b";
  if (level === "WARN") return "var(--status-warning)";
  if (level === "INFO") return "#64b5f6";
  return "var(--text-muted)";
};
const _debugLevelBg = (level) => {
  if (level === "ERROR") return "var(--status-danger-soft)";
  if (level === "WARN") return "var(--status-warning-soft)";
  if (level === "INFO") return "rgba(100,181,246,0.08)";
  return "transparent";
};
const _debugFmtTs = (ts) => new Date(ts * 1000).toTimeString().slice(0, 8);

function _debugFmtAge(ageSeconds) {
  if (ageSeconds == null) return "—";
  if (ageSeconds < 60) return `${ageSeconds}s`;
  const minutes = Math.floor(ageSeconds / 60);
  if (minutes < 60) return `${minutes}m ${ageSeconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function _debugAuthRows(info, t) {
  const authStatus =
    info.authed === true ? (
      <span
        style={{ color: "var(--status-success)", display: "flex", alignItems: "center", gap: 4 }}
      >
        <Check size={11} weight="bold" />
        {t("debugAuthedYes")}
      </span>
    ) : info.authed === false ? (
      <span
        style={{ color: "var(--status-danger)", display: "flex", alignItems: "center", gap: 4 }}
      >
        <WarningCircle size={11} weight="fill" />
        {t("debugAuthedNo")}
      </span>
    ) : (
      t("debugAuthedUnknown")
    );
  const streamError = info.lastStreamError;
  return [
    [t("debugAuthStatus"), authStatus],
    [
      t("debugCookieRefresh"),
      info.cookieRefreshAgeS == null
        ? t("debugCookieRefreshNever")
        : `${_debugFmtAge(info.cookieRefreshAgeS)} ago`,
    ],
    [
      t("debugLastStreamError"),
      streamError
        ? `${streamError.videoId} — ${streamError.error.slice(0, 60)}${streamError.error.length > 60 ? "…" : ""}`
        : t("debugLastStreamErrorNone"),
    ],
  ];
}

function _buildDebugReport(info, logs) {
  return [
    "=== Kodama Debug Report ===",
    info
      ? [
          `App:        ${APP_VERSION}`,
          `Python:     ${info.python}`,
          `yt-dlp:     ${info.ytdlp}`,
          `ytmusicapi: ${info.ytmusicapi}`,
          `Flask:      ${info.flask}`,
          `Node.js:    ${info.node || "—"}`,
          `Profil:     ${info.profile}`,
          `Plattform:  ${info.platform}`,
          `Uptime:     ${info.uptime}`,
          `Data dir:   ${info.data_dir}`,
          `\n--- Session/Auth ---`,
          `Authed:           ${info.authed === true ? "yes" : info.authed === false ? "no" : "unknown"}`,
          `Cookie-Refresh:   ${_debugFmtAge(info.cookieRefreshAgeS)} ago`,
          `Last stream err:  ${
            info.lastStreamError
              ? `${info.lastStreamError.videoId} — ${info.lastStreamError.error}`
              : "none"
          }`,
        ].join("\n")
      : "Backend nicht erreichbar",
    `\n=== Logs (${logs.length} Einträge) ===`,
    ...logs.map((l) => `[${_debugFmtTs(l.ts)}] [${l.level}] [${l.source}] ${l.msg}`),
  ].join("\n");
}

export function DebugFloatingWindow({ onClose }) {
  const t = useLang();
  const [info, setInfo] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [source, setSource] = useState("ALL");
  const [autoScroll, setAutoScroll] = useState(true);
  const [activeTab, setActiveTab] = useState("logs"); // "info" | "logs"
  const [copied, setCopied] = useState(false);
  const [pos, setPos] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("kiyoshi-debug-float-pos")) || { x: 80, y: 80 };
    } catch {
      return { x: 80, y: 80 };
    }
  });
  const logRef = useRef(null);
  const posRef = useRef(pos);
  posRef.current = pos;

  const fetchInfo = useCallback(() => {
    return fetch(`${API}/debug/info`)
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timeoutId;
    const poll = async () => {
      await fetchInfo();
      if (!cancelled) timeoutId = window.setTimeout(poll, 3000);
    };
    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [fetchInfo]);

  const allLogs = useMemo(() => {
    const backend = info?.logs || [];
    return [...frontendLogs, ...backend].sort((a, b) => a.ts - b.ts);
  }, [info]);

  const visibleLogs = useMemo(
    () =>
      allLogs.filter((l) => {
        if (filter !== "ALL" && l.level !== filter) return false;
        if (source !== "ALL" && l.source !== source) return false;
        return true;
      }),
    [allLogs, filter, source]
  );

  useEffect(() => {
    if (autoScroll && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [visibleLogs.length, autoScroll]);

  const startDrag = useCallback((e) => {
    if (e.button !== 0 || e.target.closest("button")) return;
    e.preventDefault();
    const ox = e.clientX - posRef.current.x;
    const oy = e.clientY - posRef.current.y;
    const onMove = (me) => {
      const np = { x: me.clientX - ox, y: me.clientY - oy };
      setPos(np);
      localStorage.setItem("kiyoshi-debug-float-pos", JSON.stringify(np));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  const handleCopy = () => {
    navigator.clipboard
      .writeText(_buildDebugReport(info, visibleLogs))
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
  };

  const sysRows = info
    ? [
        ["Python", info.python],
        ["yt-dlp", info.ytdlp],
        ["ytmusicapi", info.ytmusicapi],
        ["Flask", info.flask],
        ["Node.js", info.node ? info.node.split(/[/\\]/).pop() : "—"],
        ["Profil", info.profile],
        ["Plattform", info.platform],
        ["Uptime", info.uptime],
        ..._debugAuthRows(info, t),
      ]
    : [];

  return createPortal(
    <div
      style={{
        position: "fixed",
        left: pos.x,
        top: pos.y,
        zIndex: 9998,
        width: 660,
        height: 480,
        display: "flex",
        flexDirection: "column",
        background: "var(--bg-surface)",
        border: "0.5px solid var(--stroke)",
        borderRadius: "var(--r-xl)",
        boxShadow: "var(--elevation-4)",
        fontFamily: "var(--font)",
        overflow: "hidden",
        resize: "both",
        minWidth: 380,
        minHeight: 260,
      }}
    >
      {/* Title bar */}
      <div
        onMouseDown={startDrag}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 10px",
          background: "var(--surface-1)",
          borderBottom: "0.5px solid var(--stroke)",
          cursor: "grab",
          userSelect: "none",
          flexShrink: 0,
        }}
      >
        <Bug size={13} style={{ color: "var(--accent)", flexShrink: 0 }} />
        <span className="text-t12 font-semibold text-primary flex-1">Debug</span>
        <Button
          variant={activeTab === "info" ? "secondary" : "ghost"}
          size="sm"
          className="text-t11 px-2.5!"
          onPress={() => setActiveTab("info")}
        >
          Sysinfo
        </Button>
        <Button
          variant={activeTab === "logs" ? "secondary" : "ghost"}
          size="sm"
          className="text-t11 px-2.5!"
          onPress={() => setActiveTab("logs")}
        >
          Logs
        </Button>
        <div className="w-px h-3 bg-border mx-0.5" />
        <Button
          variant="ghost"
          size="sm"
          isIconOnly
          onPress={onClose}
          className="text-[var(--status-danger)]! rounded-full"
        >
          <X size={12} weight="bold" />
        </Button>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          padding: "10px 12px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          minHeight: 200,
        }}
      >
        {activeTab === "info" && (
          <div style={{ overflowY: "auto" }}>
            {!info ? (
              <div className="text-t12 text-muted p-2">{t("loading")}…</div>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
                {sysRows.map(([k, v]) => (
                  <CardRoot
                    key={k}
                    variant="secondary"
                    className="bg-surface-1 flex flex-row items-center gap-2 px-3 py-2"
                  >
                    <span className="text-t11 text-muted min-w-[72px] shrink-0">{k}</span>
                    <span className="text-t11 text-primary font-mono overflow-hidden text-ellipsis whitespace-nowrap">
                      {v}
                    </span>
                  </CardRoot>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "logs" && (
          <>
            {/* Filter bar */}
            <div className="flex items-center gap-1 mb-1.5 flex-wrap shrink-0">
              {["ALL", "INFO", "WARN", "ERROR"].map((f) => (
                <Button
                  key={f}
                  variant={filter === f ? "secondary" : "ghost"}
                  size="sm"
                  className="text-t11 px-2.5!"
                  onPress={() => setFilter(f)}
                >
                  {f}
                </Button>
              ))}
              <div className="w-px h-3 bg-border mx-0.5" />
              {["ALL", "frontend", "backend"].map((s) => (
                <Button
                  key={s}
                  variant={source === s ? "secondary" : "ghost"}
                  size="sm"
                  className="text-t11 px-2.5!"
                  onPress={() => setSource(s)}
                >
                  {s === "ALL" ? "Alle" : s}
                </Button>
              ))}
              <div className="ml-auto flex gap-1">
                <Button
                  variant={autoScroll ? "secondary" : "ghost"}
                  size="sm"
                  className="text-t11 px-2.5!"
                  onPress={() => setAutoScroll((a) => !a)}
                >
                  <CaretDown size={10} /> Scroll
                </Button>
                <Button variant="ghost" size="sm" className="text-t11 px-2.5!" onPress={handleCopy}>
                  {copied ? (
                    <>
                      <Check size={10} weight="bold" /> {t("copied")}
                    </>
                  ) : (
                    <>
                      <Copy size={10} /> {t("copyAll")}
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Log list */}
            <div
              ref={logRef}
              className="scrollable"
              style={{
                flex: 1,
                overflowY: "auto",
                background: "var(--surface-1)",
                borderRadius: "var(--r-lg)",
                padding: "4px 2px",
                fontFamily: "monospace",
                fontSize: 10,
                minHeight: 0,
              }}
              onScroll={(e) => {
                const el = e.currentTarget;
                if (el.scrollHeight - el.scrollTop - el.clientHeight > 40 && autoScroll)
                  setAutoScroll(false);
              }}
            >
              {visibleLogs.length === 0 ? (
                <div className="text-muted py-2.5 px-2 text-center">{t("debugNoLogs")}</div>
              ) : (
                visibleLogs.map((entry, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 5,
                      padding: "1px 5px",
                      borderRadius: "var(--r-xs)",
                      marginBottom: 1,
                      background: _debugLevelBg(entry.level),
                    }}
                  >
                    <span style={{ color: "var(--t3)", flexShrink: 0, userSelect: "none" }}>
                      {_debugFmtTs(entry.ts)}
                    </span>
                    <span
                      style={{
                        color: _debugLevelColor(entry.level),
                        flexShrink: 0,
                        minWidth: 36,
                        fontWeight: 700,
                        userSelect: "none",
                      }}
                    >
                      {entry.level}
                    </span>
                    <span
                      style={{
                        color:
                          entry.source === "frontend"
                            ? "rgba(224,64,251,0.7)"
                            : "rgba(100,181,246,0.6)",
                        flexShrink: 0,
                        minWidth: 50,
                        userSelect: "none",
                      }}
                    >
                      [{entry.source}]
                    </span>
                    <span style={{ color: "var(--t2)", wordBreak: "break-all", lineHeight: 1.4 }}>
                      {entry.msg}
                    </span>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>,
    document.body
  );
}

export function DebugTab({ t }) {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [source, setSource] = useState("ALL");
  const [autoScroll, setAutoScroll] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [copied, setCopied] = useState(false);
  const logRef = useRef(null);

  const fetchInfo = useCallback(() => {
    setError(null);
    fetch(`${API}/debug/info`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setInfo)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    fetchInfo();
  }, [fetchInfo, refreshKey]);

  const allLogs = useMemo(() => {
    return [...frontendLogs, ...(info?.logs || [])].sort((a, b) => a.ts - b.ts);
  }, [info]);
  const visibleLogs = useMemo(
    () =>
      allLogs.filter(
        (l) => (filter === "ALL" || l.level === filter) && (source === "ALL" || l.source === source)
      ),
    [allLogs, filter, source]
  );
  useEffect(() => {
    if (autoScroll && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [visibleLogs.length, autoScroll]);

  const handleCopy = () => {
    navigator.clipboard
      .writeText(_buildDebugReport(info, visibleLogs))
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
  };
  const openFloat = () => window.dispatchEvent(new CustomEvent("kiyoshi-debug-float"));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
      {/* ── System Info ── */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--t1)" }}>
            {t("debugSysInfo")}
          </div>
          <Button variant="secondary" size="sm" onPress={openFloat}>
            <ArrowSquareOut size={12} />
            {t("debugOpenFloat")}
          </Button>
        </div>
        {error ? (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "var(--r-lg)",
              background: "var(--status-danger-soft)",
              color: "var(--status-danger)",
              fontSize: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <WarningCircle size={14} weight="fill" style={{ flexShrink: 0 }} />
            {t("debugBackendUnreachable")}: {error}
          </div>
        ) : !info ? (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "var(--r-lg)",
              background: "var(--surface-1)",
              color: "var(--t3)",
              fontSize: 12,
            }}
          >
            {t("loading")}…
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {[
              ["Python", info.python],
              ["yt-dlp", info.ytdlp],
              ["ytmusicapi", info.ytmusicapi],
              ["Flask", info.flask],
              [
                "Node.js",
                info.node ? (
                  <span
                    style={{
                      color: "var(--status-success)",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <Check size={11} weight="bold" />
                    {info.node.split(/[/\\]/).pop()}
                  </span>
                ) : (
                  <span style={{ color: "var(--status-danger)" }}>—</span>
                ),
              ],
              ["Profil", info.profile],
              ["Plattform", info.platform],
              ["Uptime", info.uptime],
              ..._debugAuthRows(info, t),
            ].map(([k, v]) => (
              <CardRoot
                key={k}
                variant="secondary"
                className="bg-surface-1 flex flex-row items-center gap-2.5 px-3.5 py-2.5"
              >
                <span className="text-t11 text-muted min-w-[76px] shrink-0">{k}</span>
                <span className="text-t12 text-primary font-mono overflow-hidden text-ellipsis whitespace-nowrap">
                  {v}
                </span>
              </CardRoot>
            ))}
          </div>
        )}
      </div>

      {/* ── Log viewer ── */}
      <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        {/* Toolbar */}
        <div className="flex items-center gap-1 mb-2 flex-wrap">
          <span className="text-t13 font-semibold text-primary mr-1.5">Logs</span>
          {["ALL", "INFO", "WARN", "ERROR"].map((f) => (
            <Button
              key={f}
              variant={filter === f ? "secondary" : "ghost"}
              size="sm"
              className="text-t11 px-2.5!"
              onPress={() => setFilter(f)}
            >
              {f}
            </Button>
          ))}
          <div className="w-px h-3.5 bg-border mx-0.5" />
          {["ALL", "frontend", "backend"].map((s) => (
            <Button
              key={s}
              variant={source === s ? "secondary" : "ghost"}
              size="sm"
              className="text-t11 px-2.5!"
              onPress={() => setSource(s)}
            >
              {s === "ALL" ? "Alle" : s}
            </Button>
          ))}
          <div className="ml-auto flex gap-1">
            <Button
              variant={autoScroll ? "secondary" : "ghost"}
              size="sm"
              className="text-t11 px-2.5!"
              onPress={() => setAutoScroll((a) => !a)}
            >
              <CaretDown size={11} /> Auto-Scroll
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-t11 px-2.5!"
              onPress={() => setRefreshKey((k) => k + 1)}
            >
              <ArrowClockwise size={11} /> {t("refresh")}
            </Button>
            <Button variant="ghost" size="sm" className="text-t11 px-2.5!" onPress={handleCopy}>
              {copied ? (
                <>
                  <Check size={11} weight="bold" /> {t("copied")}
                </>
              ) : (
                <>
                  <Copy size={11} /> {t("copyAll")}
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Log area */}
        <div
          ref={logRef}
          className="scrollable"
          style={{
            flex: 1,
            overflowY: "auto",
            background: "var(--surface-1)",
            borderRadius: "var(--r-lg)",
            padding: "6px 4px",
            fontFamily: "monospace",
            fontSize: 11,
            minHeight: 180,
          }}
          onScroll={(e) => {
            const el = e.currentTarget;
            if (el.scrollHeight - el.scrollTop - el.clientHeight > 40 && autoScroll)
              setAutoScroll(false);
          }}
        >
          {visibleLogs.length === 0 ? (
            <div style={{ color: "var(--t3)", padding: "12px 8px", textAlign: "center" }}>
              {t("debugNoLogs")}
            </div>
          ) : (
            visibleLogs.map((entry, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 6,
                  padding: "2px 6px",
                  borderRadius: "var(--r-xs)",
                  marginBottom: 1,
                  background: _debugLevelBg(entry.level),
                }}
              >
                <span style={{ color: "var(--t3)", flexShrink: 0, userSelect: "none" }}>
                  {_debugFmtTs(entry.ts)}
                </span>
                <span
                  style={{
                    color: _debugLevelColor(entry.level),
                    flexShrink: 0,
                    minWidth: 38,
                    fontWeight: 700,
                    userSelect: "none",
                  }}
                >
                  {entry.level}
                </span>
                <span
                  style={{
                    color:
                      entry.source === "frontend"
                        ? "rgba(224,64,251,0.7)"
                        : "rgba(100,181,246,0.6)",
                    flexShrink: 0,
                    minWidth: 52,
                    userSelect: "none",
                  }}
                >
                  [{entry.source}]
                </span>
                <span style={{ color: "var(--t2)", wordBreak: "break-all", lineHeight: 1.45 }}>
                  {entry.msg}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export function UnisonIdentitySection() {
  const t = useLang();
  const [identity, setIdentity] = useState(() => {
    try {
      const raw = localStorage.getItem("kodama-unison-identity");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [serverName, setServerName] = useState(null); // resolved nickname or pet name from server
  const [nickDraft, setNickDraft] = useState("");
  const [nickBusy, setNickBusy] = useState(false);
  const [nickErr, setNickErr] = useState("");

  const NICK_RE = /^[A-Za-z0-9_]{3,20}$/;

  const persist = (id) => {
    try {
      localStorage.setItem("kodama-unison-identity", JSON.stringify(id));
    } catch {
      /* intentionally ignored */
    }
    setIdentity(id);
  };

  // Resolve the current display name from the server (custom nickname, or derived pet name).
  useEffect(() => {
    let alive = true;
    setServerName(null);
    setNickDraft("");
    setNickErr("");
    if (!identity?.keyId) return;
    (async () => {
      const name = await unisonFetchDisplayName(identity.keyId);
      if (!alive) return;
      const resolved = name || identity.displayName || "";
      setServerName(resolved);
      // Pre-fill draft only if the server name looks like a custom nickname (not the derived pet name).
      setNickDraft(resolved && resolved !== identity.displayName ? resolved : "");
    })();
    return () => {
      alive = false;
    };
  }, [identity?.keyId]);

  const hasCustomNick = !!serverName && serverName !== identity?.displayName;

  const saveNick = async () => {
    const v = nickDraft.trim();
    if (!NICK_RE.test(v)) {
      setNickErr(t("unisonNicknameInvalid"));
      return;
    }
    setNickBusy(true);
    setNickErr("");
    try {
      await unisonSetNickname(v);
      setServerName(v);
    } catch (e) {
      setNickErr(
        String(e?.message) === "nickname_taken"
          ? t("unisonNicknameTaken")
          : t("unisonNicknameError")
      );
    }
    setNickBusy(false);
  };

  const resetNick = async () => {
    setNickBusy(true);
    setNickErr("");
    try {
      await unisonResetNickname();
      setServerName(identity.displayName || "");
      setNickDraft("");
    } catch {
      setNickErr(t("unisonNicknameError"));
    }
    setNickBusy(false);
  };

  const create = async () => {
    setBusy(true);
    setErr("");
    try {
      persist(await generateIdentity());
    } catch {
      setErr(t("unisonGenericError"));
    }
    setBusy(false);
  };

  const importFile = async () => {
    setErr("");
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const path = await open({
        title: t("unisonImportKey"),
        filters: [{ name: "Key", extensions: ["json", "key"] }],
      });
      if (!path) return;
      const { readTextFile } = await import("@tauri-apps/plugin-fs");
      const id = await importIdentityFile(await readTextFile(path));
      persist(id);
    } catch {
      setErr(t("unisonImportError"));
    }
  };

  const exportFile = async () => {
    if (!identity) return;
    try {
      const { save } = await import("@tauri-apps/plugin-dialog");
      const { writeTextFile } = await import("@tauri-apps/plugin-fs");
      const base = (identity.displayName || identity.keyId.slice(0, 10)).replace(/[^\w-]/g, "_");
      const path = await save({
        defaultPath: `unison-identity-${base}.json`,
        filters: [{ name: "Key", extensions: ["json"] }],
      });
      if (!path) return;
      await writeTextFile(path, JSON.stringify(exportIdentityFile(identity), null, 2));
    } catch {
      /* intentionally ignored */
    }
  };

  const remove = () => {
    try {
      localStorage.removeItem("kodama-unison-identity");
    } catch {
      /* intentionally ignored */
    }
    setIdentity(null);
  };

  return (
    <>
      <SettingsSectionLabel>{t("unisonIdentity")}</SettingsSectionLabel>
      <SettingsSectionDesc>{t("unisonIdentityDesc")}</SettingsSectionDesc>
      <CardRoot variant="secondary" className="p-4 flex flex-col gap-3">
        {!identity ? (
          <>
            <div className="text-t12 text-muted leading-relaxed">{t("unisonNoIdentity")}</div>
            <div className="flex items-center gap-2">
              <Button
                color="accent"
                variant="solid"
                className="flex-1 justify-center"
                isDisabled={busy}
                onPress={create}
              >
                {busy ? <Spinner size="sm" /> : t("unisonCreate")}
              </Button>
              <Button
                variant="secondary"
                className="flex-1 justify-center gap-2"
                onPress={importFile}
              >
                <DownloadSimple size={15} className="rotate-180" />
                {t("unisonImportKey")}
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-accent-dim text-accent flex items-center justify-center shrink-0">
                <UserCircle size={20} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-t13 font-semibold truncate">
                  {serverName || identity.displayName || t("unisonAnonymous")}
                </div>
                <button
                  onClick={() => navigator.clipboard.writeText(identity.keyId).catch(() => {})}
                  title={t("copy")}
                  className="text-t10 text-muted font-mono truncate hover:text-primary bg-transparent border-0 p-0 cursor-default block max-w-full"
                >
                  {identity.keyId.slice(0, 10)}…{identity.keyId.slice(-6)}
                </button>
              </div>
            </div>

            {/* Custom nickname editor */}
            <div className="flex flex-col gap-1.5">
              <div className="text-t11 font-semibold text-secondary">{t("unisonNickname")}</div>
              <div className="text-t10 text-muted leading-relaxed">{t("unisonNicknameDesc")}</div>
              <div className="flex items-center gap-2 mt-0.5">
                <TextFieldRoot
                  aria-label={t("unisonNickname")}
                  className="flex-1"
                  value={nickDraft}
                  onChange={setNickDraft}
                >
                  <InputRoot
                    placeholder={identity.displayName || ""}
                    maxLength={20}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveNick();
                    }}
                  />
                </TextFieldRoot>
                <Button
                  color="accent"
                  variant="solid"
                  className="justify-center shrink-0"
                  isDisabled={
                    nickBusy || !NICK_RE.test(nickDraft.trim()) || nickDraft.trim() === serverName
                  }
                  onPress={saveNick}
                >
                  {nickBusy ? <Spinner size="sm" /> : t("save")}
                </Button>
                {hasCustomNick ? (
                  <Button
                    variant="secondary"
                    className="justify-center shrink-0"
                    isDisabled={nickBusy}
                    onPress={resetNick}
                  >
                    {t("reset")}
                  </Button>
                ) : null}
              </div>
              {nickErr ? (
                <div className="text-t10 text-[var(--status-danger)]">{nickErr}</div>
              ) : (
                <div className="text-t10 text-muted">{t("unisonNameDerived")}</div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                className="flex-1 justify-center gap-2"
                onPress={exportFile}
              >
                <DownloadSimple size={15} />
                {t("unisonExportKey")}
              </Button>
              <Button
                variant="secondary"
                className="flex-1 justify-center gap-2"
                onPress={importFile}
              >
                <DownloadSimple size={15} className="rotate-180" />
                {t("unisonImportKey")}
              </Button>
            </div>
            <Button
              variant="ghost"
              className="justify-center text-[var(--status-danger)]!"
              onPress={remove}
            >
              {t("unisonRemove")}
            </Button>
          </>
        )}
        {err ? <div className="text-t11 text-[var(--status-danger)]">{err}</div> : null}
      </CardRoot>
    </>
  );
}

// Composer-related settings (backend-backed, since the composer talks to Kodama's bridge).
export function ComposerSettingsSection() {
  const t = useLang();
  const [autocache, setAutocache] = useState(true);
  useEffect(() => {
    fetch(`${API}/composer-bridge/autocache`)
      .then((r) => r.json())
      .then((d) => setAutocache(d.enabled !== false))
      .catch(() => {});
  }, []);
  const toggle = (v) => {
    setAutocache(v);
    fetch(`${API}/composer-bridge/autocache`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: v }),
    }).catch(() => {});
  };
  return (
    <>
      <SettingsSectionLabel>{t("composer")}</SettingsSectionLabel>
      <SettingRow
        label={t("composerAutocache")}
        description={t("composerAutocacheDesc")}
        icon={<DownloadSimple />}
      >
        <Toggle value={autocache} onChange={toggle} />
      </SettingRow>
    </>
  );
}

export function FfmpegUpdateRow() {
  const t = useLang();
  const [info, setInfo] = useState(null); // { installed, latest, updateAvailable }
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState("idle"); // idle | downloading | done | error
  const [percent, setPercent] = useState(0);

  const check = useCallback(async () => {
    setLoading(true);
    try {
      setInfo(await fetch(`${API}/ffmpeg/check-update`).then((r) => r.json()));
    } catch {
      setInfo(null);
    }
    setLoading(false);
  }, []);
  useEffect(() => {
    check();
  }, [check]);

  const startUpdate = () => {
    setPhase("downloading");
    setPercent(0);
    const es = new EventSource(`${API}/ffmpeg/download?force=1`);
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.status === "progress") setPercent(d.percent || 0);
        else if (d.status === "done") {
          es.close();
          setPercent(100);
          setPhase("done");
          try {
            localStorage.setItem("kiyoshi-ffmpeg-update-dismissed", info?.latest || "");
            localStorage.setItem("kiyoshi-ffmpeg-ok", "1");
          } catch {
            /* intentionally ignored */
          }
          check();
        } else if (d.status === "error") {
          es.close();
          setPhase("error");
        }
      } catch {
        /* intentionally ignored */
      }
    };
    es.onerror = () => {
      es.close();
      setPhase("error");
    };
  };

  const desc = loading
    ? t("checking")
    : !info?.installed
      ? t("ffmpegNotInstalled") || "Nicht installiert"
      : info.updateAvailable
        ? `${info.installed} → ${info.latest}`
        : `${info.installed} · ${t("upToDate")}`;

  return (
    <>
      <SettingRow label="FFmpeg" description={desc} icon={<DownloadSimple size={15} />}>
        {phase === "downloading" ? (
          <span className="text-t12 text-muted flex items-center gap-1.5">
            <ArrowClockwise size={13} style={{ animation: "spin2 0.8s linear infinite" }} />
            {percent}%
          </span>
        ) : phase === "done" ? (
          <span
            className="text-t12 flex items-center gap-1.5"
            style={{ color: "var(--status-success)" }}
          >
            <CheckCircle size={14} weight="fill" />
            {t("ffmpegUpdated")}
          </span>
        ) : info?.updateAvailable ? (
          <Button color="accent" variant="solid" size="sm" onPress={startUpdate}>
            {t("ffmpegUpdate")}
          </Button>
        ) : !loading && info && !info.installed ? (
          <Button color="accent" variant="solid" size="sm" onPress={startUpdate}>
            {t("ffmpegDownload")}
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            isIconOnly
            className="rounded-full text-muted"
            isDisabled={loading}
            onPress={check}
          >
            <ArrowClockwise
              size={14}
              style={loading ? { animation: "spin2 0.8s linear infinite" } : undefined}
            />
          </Button>
        )}
      </SettingRow>
      {phase === "downloading" && (
        <ProgressBar aria-label="FFmpeg update" value={percent} className="w-full gap-0! mt-1.5">
          <ProgressBarTrack className="h-[3px]!">
            <ProgressBarFill />
          </ProgressBarTrack>
        </ProgressBar>
      )}
      {phase === "error" && (
        <div
          className="text-t12 mt-1.5 flex items-center gap-1.5"
          style={{ color: "var(--status-danger)" }}
        >
          {t("ffmpegUpdateFailed")}
        </div>
      )}
    </>
  );
}

// yt-dlp version + on-demand update. yt-dlp is pure Python, so the backend can swap in a
// newer wheel at runtime — lets the user fix YouTube extraction breakage ("Sign in to confirm
// you're not a bot") without waiting for a full app release.
export function YtDlpUpdateRow() {
  const t = useLang();
  const [info, setInfo] = useState(null); // { installed, latest, updateAvailable }
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState("idle"); // idle | updating | done | error

  const check = useCallback(async () => {
    setLoading(true);
    try {
      setInfo(await fetch(`${API}/ytdlp/check-update`).then((r) => r.json()));
    } catch {
      setInfo(null);
    }
    setLoading(false);
  }, []);
  useEffect(() => {
    check();
  }, [check]);

  const startUpdate = async () => {
    setPhase("updating");
    try {
      const d = await fetch(`${API}/ytdlp/update`, { method: "POST" }).then((r) => r.json());
      if (d.ok) {
        setPhase("done");
        check();
      } else setPhase("error");
    } catch {
      setPhase("error");
    }
  };

  const desc = loading
    ? t("checking")
    : !info?.installed
      ? "—"
      : info.updateAvailable
        ? `${info.installed} → ${info.latest}`
        : `${info.installed} · ${t("upToDate")}`;

  return (
    <SettingRow label="yt-dlp" description={desc} icon={<DownloadSimple size={15} />}>
      {phase === "updating" ? (
        <span className="text-t12 text-muted flex items-center gap-1.5">
          <ArrowClockwise size={13} style={{ animation: "spin2 0.8s linear infinite" }} />
        </span>
      ) : phase === "done" ? (
        <span
          className="text-t12 flex items-center gap-1.5"
          style={{ color: "var(--status-success)" }}
        >
          <CheckCircle size={14} weight="fill" />
          {t("ytdlpUpdated") || "yt-dlp updated"}
        </span>
      ) : phase === "error" ? (
        <Button color="accent" variant="solid" size="sm" onPress={startUpdate}>
          {t("ffmpegUpdate") || "Update"}
        </Button>
      ) : info?.updateAvailable ? (
        <Button color="accent" variant="solid" size="sm" onPress={startUpdate}>
          {t("ffmpegUpdate") || "Update"}
        </Button>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          isIconOnly
          className="rounded-full text-muted"
          isDisabled={loading}
          onPress={check}
        >
          <ArrowClockwise
            size={14}
            style={loading ? { animation: "spin2 0.8s linear infinite" } : undefined}
          />
        </Button>
      )}
    </SettingRow>
  );
}
