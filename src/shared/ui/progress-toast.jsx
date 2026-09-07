import { Spinner } from "@heroui/react";
import { createPortal } from "react-dom";
import { useZoom } from "@/features/settings/display-context.jsx";

export function ProgressToast({ label, percent = 0 }) {
  const zoom = useZoom();
  const progress = Math.max(0, Math.min(100, Math.round(percent)));

  return createPortal(
    <div
      style={{
        position: "fixed",
        bottom: 120 * zoom,
        insetInlineEnd: 24 * zoom,
        zIndex: 100000,
      }}
    >
      <div
        className="flex items-center gap-3 rounded-xl border border-border bg-elevated px-4 py-3 shadow-lg"
        style={{ zoom, minWidth: 220 }}
      >
        <Spinner size="sm" />
        <div className="flex-1 min-w-0">
          <div className="text-t12 text-primary truncate">{label}</div>
          <div className="h-1 mt-2 rounded-full bg-fill-subtle overflow-hidden">
            <div className="h-full bg-accent" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <span className="text-t11 text-muted tabular-nums">{progress}%</span>
      </div>
    </div>,
    document.body
  );
}
