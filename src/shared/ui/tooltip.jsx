import { useState, useRef } from "react";
import { createPortal } from "react-dom";
import { useZoom } from "@/features/settings/display-context.jsx";

export function Tooltip({ text, children }) {
  const [visible, setVisible] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const showTimer = useRef(null);
  const hideTimer = useRef(null);
  const zoom = useZoom();
  if (!text) return children;

  const hide = () => {
    clearTimeout(showTimer.current);
    if (visible) {
      setLeaving(true);
      hideTimer.current = setTimeout(() => {
        setVisible(false);
        setLeaving(false);
      }, 120);
    }
  };

  return (
    <span
      style={{ display: "contents" }}
      onMouseEnter={(e) => {
        clearTimeout(hideTimer.current);
        setLeaving(false);
        const el = e.currentTarget.firstElementChild || e.target;
        const r = el.getBoundingClientRect();
        setPos({ x: r.left + r.width / 2, y: r.top });
        clearTimeout(showTimer.current);
        showTimer.current = setTimeout(() => setVisible(true), 350);
      }}
      onMouseLeave={hide}
    >
      {children}
      {visible &&
        createPortal(
          <div
            style={{
              position: "fixed",
              left: pos.x,
              top: pos.y - 6,
              transform: "translate(-50%, -100%)",
              pointerEvents: "none",
              zIndex: 99999,
              animation: `${leaving ? "tooltipOut" : "tooltipIn"} 0.12s ease forwards`,
            }}
          >
            <div
              style={{
                zoom,
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
                padding: "5px 9px",
                borderRadius: "var(--r-md)",
                fontSize: "var(--t11)",
                fontWeight: 500,
                border: "0.5px solid var(--border)",
                whiteSpace: "nowrap",
                boxShadow: "var(--elevation-2)",
              }}
            >
              {text}
            </div>
          </div>,
          document.body
        )}
    </span>
  );
}

// Coordinates stay outside the zoomed shell; only the label scales.
export function SidebarTooltip({ tooltip }) {
  const zoom = useZoom();
  if (!tooltip) return null;
  return createPortal(
    <div
      style={{
        position: "fixed",
        left: tooltip.x,
        top: tooltip.y,
        transform: "translateY(-50%)",
        pointerEvents: "none",
        zIndex: 9999,
      }}
    >
      <div
        style={{
          zoom,
          background: "var(--bg-elevated)",
          color: "var(--text-primary)",
          padding: "4px 10px",
          borderRadius: "var(--r-md)",
          fontSize: "var(--t12)",
          whiteSpace: "nowrap",
          border: "1px solid var(--border)",
          boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
        }}
      >
        {tooltip.text}
      </div>
    </div>,
    document.body
  );
}
