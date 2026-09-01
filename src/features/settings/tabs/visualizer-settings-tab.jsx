import {
  ArrowClockwise,
  CaretDown,
  CaretUp,
  DownloadSimple,
  Eye,
  EyeSlash,
  MusicNote,
  PaintBrushBroad,
  Sparkles,
  Trash,
  WaveformLines,
} from "@/shared/icons/icons.jsx";
import { Button } from "@heroui/react";
import { CoverView, VIZ_DEFAULTS } from "@/features/player/player-ui.jsx";
import { SettingRow, Slider, Toggle } from "@/shared/ui/settings-controls.jsx";
import { thumb } from "@/shared/api/thumbnails.js";
export function VisualizerSettingsTab({
  ambientVisualizer,
  canvasEnabled,
  canvasSource,
  applyVizPreset,
  deleteVizPreset,
  exportVizPreset,
  handleVizImport,
  instrumentalViz,
  onToggleAmbientVisualizer,
  onCanvasEnabledChange,
  onCanvasSourceChange,
  onToggleInstrumentalViz,
  onUpdateViz,
  saveVizPreset,
  setVizPresetName,
  t,
  toggleVizPreview,
  vizConfig,
  vizImportRef,
  vizPresetName,
  vizPresets,
  vizPreviewCover,
  vizPreviewHReplica,
  vizPreviewOpen,
  vizPreviewPlaying,
  vizPreviewRef,
  vizPreviewTrack,
  vizScale,
}) {
  return (
    <>
      {/* Live preview — reflects the current track + config in real time.
                    Collapsible so the options below are always reachable on short windows. */}
      {vizPreviewOpen ? (
        <div
          ref={vizPreviewRef}
          className="mb-4 rounded-xl overflow-hidden border border-border sticky z-10 shrink-0"
          style={{
            height: vizPreviewHReplica,
            top: -8,
            background: "var(--bg-base)",
          }}
        >
          {vizPreviewTrack?.thumbnail && (
            <>
              <div
                style={{
                  position: "absolute",
                  inset: "-10%",
                  backgroundImage: `url(${thumb(vizPreviewTrack.thumbnail)})`,
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                  filter: "blur(56px) saturate(1.4) brightness(0.7)",
                  transform: "scale(1.2)",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "rgba(0,0,0,0.42)",
                }}
              />
            </>
          )}
          <div
            style={{
              position: "absolute",
              inset: 0,
            }}
          >
            {vizPreviewTrack ? (
              <CoverView
                track={vizPreviewTrack}
                isPlaying={vizPreviewPlaying}
                onClose={() => {}}
                ambientVisualizer
                coverSize={vizPreviewCover}
                vizConfig={{
                  ...vizConfig,
                  barLength: (vizConfig.barLength ?? 90) * vizScale,
                  gap: (vizConfig.gap ?? 8) * vizScale,
                  barThickness: Math.max(1, (vizConfig.barThickness ?? 3) * vizScale),
                }}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-t13 text-muted">
                {t("visualizerPreviewHint") || "Play a song to preview the visualizer"}
              </div>
            )}
          </div>
          <button
            onClick={toggleVizPreview}
            title={t("hidePreview") || "Vorschau einklappen"}
            className="absolute top-2 right-2 z-20 flex items-center gap-1 rounded-full px-2.5 py-1 text-t12 text-white"
            style={{
              background: "rgba(0,0,0,0.5)",
              backdropFilter: "blur(8px)",
            }}
          >
            <EyeSlash size={14} />
            <CaretUp size={12} />
          </button>
        </div>
      ) : (
        <button
          onClick={toggleVizPreview}
          className="mb-4 w-full flex items-center justify-center gap-2 rounded-xl border border-border text-t13 text-secondary hover:bg-hover transition-colors"
          style={{
            height: 44,
          }}
        >
          <Eye size={16} />
          {t("showPreview") || "Vorschau anzeigen"}
          <CaretDown size={13} />
        </button>
      )}
      {/* Presets — save / apply / import / export named visualizer configs. */}
      <div className="mb-5">
        <div
          className="text-t13 font-semibold mb-2.5"
          style={{
            color: "var(--text-secondary)",
          }}
        >
          {t("visualizerPresets") || "Presets"}
        </div>
        <div className="flex gap-2 items-center mb-2">
          <input
            value={vizPresetName}
            onChange={(e) => setVizPresetName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveVizPreset();
            }}
            placeholder={t("presetNamePlaceholder") || "Preset benennen…"}
            style={{
              flex: 1,
              minWidth: 0,
              height: 34,
              padding: "0 12px",
              borderRadius: "var(--r-lg)",
              fontSize: "var(--t13)",
              color: "var(--text-primary)",
              background: "var(--bg-elevated)",
              border: "0.5px solid var(--border)",
              outline: "none",
            }}
          />
          <Button variant="secondary" size="sm" className="shrink-0" onPress={saveVizPreset}>
            {t("save") || "Speichern"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 shrink-0"
            onPress={() => vizImportRef.current?.click()}
          >
            <DownloadSimple size={13} className="rotate-180" />
            {t("import") || "Importieren"}
          </Button>
          <input
            ref={vizImportRef}
            type="file"
            accept=".json"
            multiple
            className="hidden"
            onChange={handleVizImport}
          />
        </div>
        {vizPresets.length > 0 && (
          <div className="flex flex-col gap-1">
            {vizPresets.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 rounded-lg"
                style={{
                  background: "var(--bg-elevated)",
                }}
              >
                <button
                  className="flex-1 min-w-0 text-left text-t13 font-medium truncate hover:text-accent transition-colors"
                  onClick={() => applyVizPreset(p)}
                >
                  {p.name}
                </button>
                <Button
                  isIconOnly
                  size="sm"
                  variant="ghost"
                  className="h-7! w-7! min-w-0!"
                  onPress={() => exportVizPreset(p)}
                  title={t("export") || "Exportieren"}
                >
                  <DownloadSimple size={13} />
                </Button>
                <Button
                  isIconOnly
                  size="sm"
                  variant="ghost"
                  className="h-7! w-7! min-w-0! text-muted hover:text-[var(--status-danger)]"
                  onPress={() => deleteVizPreset(p.id)}
                  title={t("delete") || "Löschen"}
                >
                  <Trash size={13} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
      <SettingRow
        label={t("visualizer")}
        description={t("visualizerDesc")}
        icon={<WaveformLines />}
      >
        <Toggle value={ambientVisualizer} onChange={onToggleAmbientVisualizer} />
      </SettingRow>
      <SettingRow
        label={t("instrumentalViz") || "Instrumental cover"}
        description={
          t("instrumentalVizDesc") ||
          "Show the cover + visualizer during instrumental passages in the lyrics view"
        }
        icon={<MusicNote />}
      >
        <Toggle value={instrumentalViz} onChange={onToggleInstrumentalViz} />
      </SettingRow>
      <SettingRow
        label={t("canvasArtwork") || "Animated cover"}
        description={
          t("canvasArtworkDesc") || "Show animated cover artwork in the About Song card"
        }
        icon={<MusicNote />}
      >
        <Toggle value={canvasEnabled} onChange={onCanvasEnabledChange} />
      </SettingRow>
      {canvasEnabled && (
        <SettingRow label={t("canvasSource") || "Canvas source"} icon={<MusicNote />}>
          <div className="flex flex-wrap justify-end gap-1.5">
            {[
              ["auto", t("canvasSourceAuto") || "Auto"],
              ["apple_music", t("canvasSourceAppleMusic") || "Apple Music"],
              ["tidal", t("canvasSourceTidal") || "Tidal"],
              ["vivimusic", t("canvasSourceViviMusic") || "ViviMusic"],
            ].map(([source, label]) => (
              <Button
                key={source}
                variant={canvasSource === source ? "secondary" : "ghost"}
                size="sm"
                onPress={() => onCanvasSourceChange(source)}
              >
                {label}
              </Button>
            ))}
          </div>
        </SettingRow>
      )}
      <SettingRow label={t("visualizerShape") || "Shape"} icon={<WaveformLines />}>
        <div className="flex gap-1.5">
          <Button
            variant={vizConfig.shape === "frame" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                shape: "frame",
              })
            }
          >
            {t("visualizerFrame") || "Frame"}
          </Button>
          <Button
            variant={vizConfig.shape === "ring" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                shape: "ring",
              })
            }
          >
            {t("visualizerRing") || "Ring"}
          </Button>
          <Button
            variant={vizConfig.shape === "linear" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                shape: "linear",
              })
            }
          >
            {t("visualizerLinear") || "Linear"}
          </Button>
        </div>
      </SettingRow>
      {vizConfig.shape === "linear" && (
        <SettingRow label={t("visualizerPlacement") || "Placement"} icon={<WaveformLines />}>
          <div className="flex gap-1.5">
            <Button
              variant={(vizConfig.linearPos || "bottom") === "bottom" ? "secondary" : "ghost"}
              size="sm"
              onPress={() =>
                onUpdateViz({
                  linearPos: "bottom",
                })
              }
            >
              {t("visualizerPosBottom") || "Bottom"}
            </Button>
            <Button
              variant={vizConfig.linearPos === "center" ? "secondary" : "ghost"}
              size="sm"
              onPress={() =>
                onUpdateViz({
                  linearPos: "center",
                })
              }
            >
              {t("visualizerPosCenter") || "Behind cover"}
            </Button>
          </div>
        </SettingRow>
      )}
      <SettingRow label={t("visualizerMirror") || "Mirror"} icon={<WaveformLines />}>
        <Toggle
          value={!!vizConfig.mirror}
          onChange={(v) =>
            onUpdateViz({
              mirror: v,
            })
          }
        />
      </SettingRow>
      <SettingRow label={t("visualizerBars") || "Bars"} icon={<WaveformLines />}>
        <Slider
          min={8}
          max={160}
          step={2}
          value={vizConfig.barCount}
          onChange={(v) =>
            onUpdateViz({
              barCount: v,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerLength") || "Bar length"} icon={<WaveformLines />}>
        <Slider
          min={8}
          max={260}
          step={4}
          value={vizConfig.barLength}
          onChange={(v) =>
            onUpdateViz({
              barLength: v,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerThickness") || "Bar thickness"} icon={<WaveformLines />}>
        <Slider
          min={1}
          max={16}
          step={1}
          value={vizConfig.barThickness}
          onChange={(v) =>
            onUpdateViz({
              barThickness: v,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow
        label={
          vizConfig.shape === "linear"
            ? t("visualizerGapBottom") || "Gap from bottom"
            : t("visualizerGap") || "Gap"
        }
        icon={<WaveformLines />}
      >
        <Slider
          min={0}
          max={80}
          step={2}
          value={vizConfig.gap}
          onChange={(v) =>
            onUpdateViz({
              gap: v,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerResponse") || "Responsiveness"} icon={<WaveformLines />}>
        <Slider
          min={0}
          max={100}
          step={5}
          value={Math.round((vizConfig.responsiveness ?? 0.75) * 100)}
          onChange={(v) =>
            onUpdateViz({
              responsiveness: v / 100,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow
        label={t("visualizerFloor") || "Floor"}
        description={t("visualizerFloorDesc")}
        icon={<WaveformLines />}
      >
        <Slider
          min={0}
          max={90}
          step={2}
          value={Math.round((vizConfig.floor ?? 0) * 100)}
          onChange={(v) =>
            onUpdateViz({
              floor: v / 100,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerCeiling") || "Ceiling"} icon={<WaveformLines />}>
        <Slider
          min={10}
          max={100}
          step={2}
          value={Math.round((vizConfig.ceiling ?? 1) * 100)}
          onChange={(v) =>
            onUpdateViz({
              ceiling: v / 100,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerTilt") || "Tilt (boost highs)"} icon={<WaveformLines />}>
        <Slider
          min={0}
          max={100}
          step={5}
          value={Math.round((vizConfig.tilt ?? 0) * 100)}
          onChange={(v) =>
            onUpdateViz({
              tilt: v / 100,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerBandSmooth") || "Band smoothing"} icon={<WaveformLines />}>
        <Slider
          min={0}
          max={100}
          step={5}
          value={Math.round((vizConfig.smoothBands ?? 0) * 100)}
          onChange={(v) =>
            onUpdateViz({
              smoothBands: v / 100,
            })
          }
          width={200}
        />
      </SettingRow>
      <SettingRow label={t("visualizerRender") || "Render mode"} icon={<WaveformLines />}>
        <div className="flex gap-1.5">
          <Button
            variant={(vizConfig.render || "bars") === "bars" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                render: "bars",
              })
            }
          >
            {t("visualizerBarsMode") || "Bars"}
          </Button>
          <Button
            variant={vizConfig.render === "curve" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                render: "curve",
              })
            }
          >
            {t("visualizerCurve") || "Curve"}
          </Button>
        </div>
      </SettingRow>
      <SettingRow label={t("visualizerPeakHold") || "Peak hold"} icon={<WaveformLines />}>
        <Toggle
          value={!!vizConfig.peakHold}
          onChange={(v) =>
            onUpdateViz({
              peakHold: v,
            })
          }
        />
      </SettingRow>
      <SettingRow label={t("visualizerColor") || "Color"} icon={<PaintBrushBroad />}>
        <div className="flex items-center gap-1.5">
          <Button
            variant={vizConfig.color === "accent" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                color: "accent",
              })
            }
          >
            {t("accent") || "Accent"}
          </Button>
          <Button
            variant={vizConfig.color === "cover" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                color: "cover",
              })
            }
          >
            {t("visualizerCover") || "Cover"}
          </Button>
          <Button
            variant={vizConfig.color === "custom" ? "secondary" : "ghost"}
            size="sm"
            onPress={() =>
              onUpdateViz({
                color: "custom",
              })
            }
          >
            {t("custom") || "Custom"}
          </Button>
          {vizConfig.color === "custom" && (
            <input
              type="color"
              value={vizConfig.customColor || "#e040fb"}
              onChange={(e) =>
                onUpdateViz({
                  customColor: e.target.value,
                })
              }
              className="w-7 h-7 rounded-md cursor-pointer border border-border bg-transparent p-0.5 shrink-0"
            />
          )}
        </div>
      </SettingRow>
      <SettingRow
        label={t("visualizerGradient") || "Gradient"}
        description={t("visualizerGradientDesc")}
        icon={<PaintBrushBroad />}
      >
        <div className="flex items-center gap-2">
          {vizConfig.gradient && (
            <input
              type="color"
              value={vizConfig.gradColor || "#ffffff"}
              onChange={(e) =>
                onUpdateViz({
                  gradColor: e.target.value,
                })
              }
              className="w-7 h-7 rounded-md cursor-pointer border border-border bg-transparent p-0.5 shrink-0"
            />
          )}
          <Toggle
            value={!!vizConfig.gradient}
            onChange={(v) =>
              onUpdateViz({
                gradient: v,
              })
            }
          />
        </div>
      </SettingRow>
      <SettingRow label={t("coverPulse") || "Cover pulse"} icon={<Sparkles />}>
        <Toggle
          value={vizConfig.coverPulse !== false}
          onChange={(v) =>
            onUpdateViz({
              coverPulse: v,
            })
          }
        />
      </SettingRow>
      {vizConfig.coverPulse !== false && (
        <SettingRow label={t("coverPulseStrength") || "Pulse strength"} icon={<Sparkles />}>
          <Slider
            min={0}
            max={100}
            step={5}
            value={Math.round((vizConfig.coverPulseStrength ?? 0.3) * 100)}
            onChange={(v) =>
              onUpdateViz({
                coverPulseStrength: v / 100,
              })
            }
            width={200}
          />
        </SettingRow>
      )}
      <SettingRow label={t("visualizerBlobs") || "Ambient blobs"} icon={<Sparkles />}>
        <Toggle
          value={vizConfig.blobs !== false}
          onChange={(v) =>
            onUpdateViz({
              blobs: v,
            })
          }
        />
      </SettingRow>
      <div className="flex justify-end mt-4">
        <Button
          variant="secondary"
          size="sm"
          className="gap-1.5"
          onPress={() =>
            onUpdateViz({
              ...VIZ_DEFAULTS,
            })
          }
        >
          <ArrowClockwise size={13} /> {t("resetToDefault") || "Auf Standard zurücksetzen"}
        </Button>
      </div>
    </>
  );
}
