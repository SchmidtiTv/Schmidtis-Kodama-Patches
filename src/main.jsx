import "@kodama/e2e-network-guard";
import "@kodama/e2e-runtime-controls";
import "@kodama/e2e-bridge";

import { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { Spinner } from "@heroui/react";
import App from "@/app/App.jsx";
import { installErrorCapture } from "@/app/diagnostics/error-capture.js";
import "@/app/styles/index.css";

const OverlayEditorApp = lazy(() => import("@/features/overlay/OverlayEditorApp.jsx"));
const MiniPlayerApp = lazy(() => import("@/features/player/miniplayer/MiniPlayerApp.jsx"));
const modeLoadingFallback = (
  <div
    role="status"
    aria-label="Loading"
    style={{ position: "fixed", inset: 0, display: "grid", placeItems: "center" }}
  >
    <Spinner size="lg" />
  </div>
);

installErrorCapture(); // capture frontend errors for the bug-report tool

// Suppress WebView2/WebKit's native right-click menu (Back/Refresh/Save as/Print) in
// packaged builds — it's a browser artifact that doesn't belong in a desktop app and has
// no use for end users. Left enabled in dev so right-click → Inspect still works there.
if (!import.meta.env.DEV) {
  window.addEventListener("contextmenu", (e) => e.preventDefault());
}

console.log(
  "[boot] main.jsx executing at +" + (Date.now() - (window.__bootStart || Date.now())) + "ms"
);

const params = new URLSearchParams(window.location.search);
const isOverlayEditor = params.get("overlayEditor") === "1";
// The mini player is its own small window and shares nothing with the main tree — render it
// alone, without App (a second App would start a second audio pipeline).
const isMiniPlayer = params.get("miniPlayer") === "1";

ReactDOM.createRoot(document.getElementById("root")).render(
  isMiniPlayer ? (
    <Suspense fallback={modeLoadingFallback}>
      <MiniPlayerApp />
    </Suspense>
  ) : (
    <>
      {isOverlayEditor ? (
        <Suspense fallback={modeLoadingFallback}>
          <OverlayEditorApp />
        </Suspense>
      ) : (
        <App />
      )}
    </>
  )
);

// Fade out the HTML boot splash now that React has taken over.
// Done in a microtask so React has had at least one paint cycle.
requestAnimationFrame(() =>
  requestAnimationFrame(() => {
    document.documentElement.classList.add("loaded");
    console.log(
      "[boot] React mounted at +" + (Date.now() - (window.__bootStart || Date.now())) + "ms"
    );
    setTimeout(() => {
      const s = document.getElementById("boot-splash");
      if (s) s.remove();
    }, 400);
  })
);
