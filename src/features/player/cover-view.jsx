import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { thumb } from "@/shared/api/thumbnails.js";
import { RetryingImage } from "@/shared/ui/retrying-image.jsx";
import { ExplicitBadge } from "@/features/music/components/rows.jsx";
import { acquireAudioAnalysis, audioLevels } from "@/features/player/audio-levels.js";
import { hiResThumb } from "./cover-art.js";
import { useLang } from "@/shared/i18n/context.jsx";

import { VIZ_DEFAULTS, drawSpectrum } from "@/features/visualizer";
export { VIZ_DEFAULTS } from "@/features/visualizer";

export function CoverView({
  track,
  isPlaying,
  ambientVisualizer = true,
  vizConfig,
  coverSize = 260,
  compact = false,
  isActive = true,
  ambientBackground = false,
  playbackOrigin = null,
}) {
  const t = useLang();
  const albumOrigin = playbackOrigin?.kind === "album" ? playbackOrigin : null;
  const albumTrackNumber = albumOrigin ? albumOrigin.trackIds.indexOf(track.videoId) + 1 : 0;
  const hq = hiResThumb(track.thumbnail);
  const specRef = useRef(null);
  const coverRef = useRef(null);
  const playingRef = useRef(isPlaying);
  const cfgRef = useRef(null);
  const coverColorRef = useRef(null);
  const rootRef = useRef(null);
  const [roomForInfo, setRoomForInfo] = useState(true);
  useEffect(() => {
    const element = rootRef.current;
    if (!element || compact || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const height = entry.contentRect.height;
      setRoomForInfo((visible) => (visible ? height >= 520 : height > 550));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [compact]);
  useLayoutEffect(() => {
    playingRef.current = isPlaying;
    cfgRef.current = { ...VIZ_DEFAULTS, ...(vizConfig || {}) };
  }, [isPlaying, vizConfig]);

  // Extract a vibrant colour from the cover for the "dynamic" colour mode.
  useEffect(() => {
    const url = track.thumbnail ? thumb(track.thumbnail) : null;
    if (!url) {
      coverColorRef.current = null;
      return;
    }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        c.width = 40;
        c.height = 40;
        const cx = c.getContext("2d");
        cx.drawImage(img, 0, 0, 40, 40);
        const d = cx.getImageData(0, 0, 40, 40).data;
        let br = 0,
          bg = 0,
          bb = 0,
          best = -1,
          sr = 0,
          sg = 0,
          sb = 0,
          cnt = 0;
        for (let i = 0; i < d.length; i += 4) {
          const r = d[i],
            g = d[i + 1],
            b = d[i + 2];
          sr += r;
          sg += g;
          sb += b;
          cnt++;
          const mx = Math.max(r, g, b),
            mn = Math.min(r, g, b);
          const score = (mx === 0 ? 0 : (mx - mn) / mx) * (mx / 255); // saturation × brightness
          if (score > best) {
            best = score;
            br = r;
            bg = g;
            bb = b;
          }
        }
        const useV = best > 0.18;
        const R = useV ? br : Math.round(sr / cnt),
          G = useV ? bg : Math.round(sg / cnt),
          B = useV ? bb : Math.round(sb / cnt);
        coverColorRef.current = `rgb(${R},${G},${B})`;
      } catch {
        coverColorRef.current = null;
      }
    };
    img.onerror = () => {
      coverColorRef.current = null;
    };
    img.src = url;
  }, [track.thumbnail]);

  // Audio-reactive spectrum (ring or cover-hugging frame) + cover pulse, driven by the live
  // `audioLevels` (Rust FFT). Do not keep a hidden or paused pane rendering at 60fps.
  // Config read via a ref so changes apply without restarting rAF.
  useEffect(() => {
    if (!ambientVisualizer || !isActive || !isPlaying) return;
    return acquireAudioAnalysis();
  }, [ambientVisualizer, isActive, isPlaying]);

  useEffect(() => {
    if (!ambientVisualizer || !isActive || !isPlaying) return;
    const cv = specRef.current;
    const cover = coverRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    const accentVar =
      getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#e040fb";
    let raf = 0,
      smoothLevel = 0,
      lastDrawAt = -Infinity;
    const sm = [],
      pk = [];
    const draw = (now) => {
      // Rust emits a fresh spectrum at ~30fps. Drawing at the display's 60/120Hz only repeats
      // identical data and makes a full-size canvas needlessly expensive.
      if (now - lastDrawAt < 1000 / 30) {
        raf = requestAnimationFrame(draw);
        return;
      }
      lastDrawAt = now;
      const cfg = cfgRef.current;
      const dpr = window.devicePixelRatio || 1;
      const w = cv.clientWidth,
        h = cv.clientHeight;
      if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
        cv.width = Math.round(w * dpr);
        cv.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const src = audioLevels.bands || [],
        srcN = src.length || 48;
      let n = Math.max(8, cfg.barCount | 0 || 48);
      if (cfg.shape === "linear") {
        const fullWidth = Math.max(320, window.screen?.availWidth || window.innerWidth || w);
        n = Math.max(8, Math.round(n * Math.min(1, w / fullWidth)));
      }
      const resp = Math.max(0, Math.min(1, cfg.responsiveness != null ? cfg.responsiveness : 0.75));
      const rel = (1 - resp) * 0.95; // 0 = instant, 0.95 = very floaty
      const bandAt = (i) => {
        const f = (i / n) * srcN,
          lo = Math.floor(f),
          hi = Math.min(srcN - 1, lo + 1),
          t = f - lo;
        return (src[lo] || 0) * (1 - t) + (src[hi] || 0) * t;
      };
      // ── value pipeline: tilt → floor/ceiling → temporal smoothing → spatial blur ──
      const tilt = cfg.tilt || 0,
        fl = cfg.floor || 0,
        ce = cfg.ceiling != null ? cfg.ceiling : 1,
        rng = Math.max(0.02, ce - fl);
      for (let i = 0; i < n; i++) {
        let v = Math.max(0, Math.min(1, bandAt(i)));
        if (tilt) v = Math.min(1, v * (1 + tilt * (i / Math.max(1, n - 1)) * 3));
        v = Math.max(0, Math.min(1, (v - fl) / rng));
        const p = sm[i] || 0;
        sm[i] = v > p ? v : p * rel + v * (1 - rel);
      }
      const sbr = Math.round((cfg.smoothBands || 0) * 8);
      const vals = new Array(n);
      if (sbr > 0) {
        for (let i = 0; i < n; i++) {
          let s = 0,
            wsum = 0;
          for (let k = -sbr; k <= sbr; k++) {
            const j = i + k;
            if (j < 0 || j >= n) continue;
            const wk = 1 - Math.abs(k) / (sbr + 1);
            s += (sm[j] || 0) * wk;
            wsum += wk;
          }
          vals[i] = s / wsum;
        }
      } else {
        for (let i = 0; i < n; i++) vals[i] = sm[i] || 0;
      }
      const peakOn = !!cfg.peakHold;
      if (peakOn) for (let i = 0; i < n; i++) pk[i] = Math.max(vals[i], (pk[i] || 0) * 0.94);

      const baseCol =
        cfg.color === "cover"
          ? coverColorRef.current || accentVar
          : cfg.color === "custom"
            ? cfg.customColor || accentVar
            : accentVar;
      let bx = (w - 260) / 2,
        by = (h - 260) / 2,
        bw = 260,
        bh = 260;
      const cover = coverRef.current;
      if (cover) {
        const r = cover.getBoundingClientRect(),
          cr = cv.getBoundingClientRect();
        bx = r.left - cr.left;
        by = r.top - cr.top;
        bw = r.width;
        bh = r.height;
      }

      drawSpectrum(ctx, {
        w,
        h,
        box: { x: bx, y: by, w: bw, h: bh },
        cfg,
        n,
        vals,
        peaks: peakOn ? pk : null,
        baseCol,
      });

      smoothLevel += ((audioLevels.level || 0) - smoothLevel) * 0.25;
      const base = playingRef.current ? 1.03 : 0.97;
      // Pulse amplitude: strength (0..1) scales up to a 0.20 cover-scale swing at full level.
      // Default 0.3 ≈ the previous fixed 0.06 factor.
      const pulseAmt =
        cfg.coverPulse && document.documentElement.dataset.reduceMotion !== "true"
          ? smoothLevel * (cfg.coverPulseStrength ?? 0.3) * 0.2
          : 0;
      if (cover) cover.style.transform = `scale(${base + pulseAmt})`;

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      if (cover) cover.style.transform = "";
    };
  }, [ambientVisualizer, isActive, isPlaying]);

  return (
    <div
      ref={rootRef}
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Ambient colour blobs — negative inset keeps edges outside the visible area */}
      {ambientVisualizer && isActive && !ambientBackground && vizConfig?.blobs !== false && (
        <>
          <div
            style={{
              position: "absolute",
              inset: "-30%",
              zIndex: 1,
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 38% 32% at 44% 42%, var(--accent) 0%, transparent 70%)",
              mixBlendMode: "screen",
              animation: "blobDrift1 18s ease-in-out infinite",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: "-30%",
              zIndex: 1,
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 32% 38% at 62% 60%, #7b2ff7 0%, transparent 68%)",
              mixBlendMode: "screen",
              animation: "blobDrift2 23s ease-in-out infinite",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: "-30%",
              zIndex: 1,
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 44% 36% at 52% 48%, #1565c0 0%, transparent 65%)",
              mixBlendMode: "screen",
              animation: "blobDrift3 29s ease-in-out infinite",
            }}
          />
        </>
      )}

      {/* Audio-reactive spectrum ring */}
      {ambientVisualizer && (
        <canvas
          ref={specRef}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            zIndex: 2,
            pointerEvents: "none",
          }}
        />
      )}

      {/* Content — shifted up when a bottom linear spectrum would otherwise overlap it */}
      <div
        style={{
          position: "relative",
          zIndex: 3,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: compact ? 32 : 64,
          marginBottom:
            ambientVisualizer &&
            vizConfig?.shape === "linear" &&
            (vizConfig?.linearPos || "bottom") === "bottom"
              ? compact
                ? 56
                : 96
              : 0,
          transition: "margin-bottom 0.3s ease",
        }}
      >
        {/* Album cover */}
        <div
          ref={coverRef}
          style={{
            width: coverSize,
            height: coverSize,
            borderRadius: vizConfig?.coverShape === "circle" ? "50%" : compact ? 12 : 16,
            overflow: "hidden",
            boxShadow: "var(--elevation-5)",
            transform: isPlaying ? "scale(1.03)" : "scale(0.97)",
            transition: ambientVisualizer
              ? "border-radius 0.3s ease"
              : "transform 0.6s cubic-bezier(0.4,0,0.2,1), border-radius 0.3s ease",
          }}
        >
          {hq ? (
            <RetryingImage
              src={thumb(hq)}
              alt=""
              loading="eager"
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <div
              style={{
                width: "100%",
                height: "100%",
                background: "var(--placeholder-gradient)",
              }}
            />
          )}
        </div>

        {/* Track info */}
        {roomForInfo && (
          <div style={{ textAlign: "center", maxWidth: compact ? 360 : 520 }}>
            <div
              style={{
                fontSize: compact ? 17 : "var(--t22)",
                fontWeight: 700,
                color: "#fff",
                marginBottom: compact ? 3 : 6,
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                lineHeight: 1.3,
              }}
            >
              <span style={{ overflowWrap: "anywhere" }}>{track.title}</span>
              {track.isExplicit && <ExplicitBadge />}
            </div>
            <div
              style={{
                fontSize: compact ? 12 : "var(--t14)",
                color: "rgba(255,255,255,0.6)",
                overflowWrap: "anywhere",
              }}
            >
              {track.artists}
            </div>
            {albumOrigin && albumTrackNumber > 0 && (
              <div
                style={{
                  fontSize: compact ? 11 : "var(--t12)",
                  color: "rgba(255,255,255,0.4)",
                  marginTop: 4,
                  overflowWrap: "anywhere",
                }}
              >
                {albumOrigin.title} ·{" "}
                {t("trackOfTotal", { n: albumTrackNumber, total: albumOrigin.trackIds.length })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// LyricsOverlay (+ word-timing/paint helpers and the Composer bridge) moved to
