export const STORE_CHANGED = "kodama://store-changed";
const STORAGE_KINDS = {
  "kodama-installed-themes": "themes",
  "kodama-visualizer-presets": "visualizer",
  "kiyoshi-visualizer-config": "visualizer",
  "kodama-equalizer": "equalizer",
};

export async function announceStoreChange(kind) {
  if (typeof window !== "undefined")
    window.dispatchEvent(new CustomEvent(STORE_CHANGED, { detail: { kind } }));
  try {
    const { emit } = await import("@tauri-apps/api/event");
    await emit(STORE_CHANGED, { kind });
  } catch {
    /* Browser previews have no native event bridge. */
  }
}

export function onStoreChanged(callback) {
  let disposed = false;
  let stop = () => {};
  const local = (event) => callback(event.detail?.kind);
  const storage = (event) => {
    if (STORAGE_KINDS[event.key]) callback(STORAGE_KINDS[event.key]);
  };
  window.addEventListener(STORE_CHANGED, local);
  window.addEventListener("storage", storage);
  import("@tauri-apps/api/event")
    .then(({ listen }) => listen(STORE_CHANGED, (event) => callback(event.payload?.kind)))
    .then((unlisten) => {
      if (disposed) unlisten();
      else stop = unlisten;
    })
    .catch(() => {});
  return () => {
    disposed = true;
    stop();
    window.removeEventListener(STORE_CHANGED, local);
    window.removeEventListener("storage", storage);
  };
}
