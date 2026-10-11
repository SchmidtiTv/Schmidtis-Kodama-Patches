const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

// The stage renderer reads matchMedia directly for positional motion. Keep its window methods
// bound to the real browser while resolving that one query through Kodama's explicit preference.
export function createBraccatoMotionWindow(browserWindow, root) {
  return new Proxy(browserWindow, {
    get(target, property) {
      if (property === "matchMedia")
        return (query) => {
          const media = target.matchMedia(query);
          if (query !== REDUCED_MOTION_QUERY) return media;
          return new Proxy(media, {
            get(list, key) {
              if (key === "matches") {
                const preference = root.dataset.reduceMotion;
                if (preference === "true" || preference === "false") return preference === "true";
              }
              const value = Reflect.get(list, key, list);
              return typeof value === "function" ? value.bind(list) : value;
            },
          });
        };
      const value = Reflect.get(target, property, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}
