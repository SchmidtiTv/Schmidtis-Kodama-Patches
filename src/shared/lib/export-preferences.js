export const EXPORT_DIRECTORY_KEY = "kiyoshi-mp3-dir";
export const REMEMBER_EXPORT_DIRECTORY_KEY = "kodama-remember-export-directory";
export const EXPORT_FILENAME_PATTERN_KEY = "kodama-export-filename-pattern";

export const EXPORT_FILENAME_PATTERNS = new Set(["artist-title", "title-artist", "title"]);

export function artistName(track) {
  if (Array.isArray(track?.artists)) {
    return track.artists
      .map((artist) => (typeof artist === "string" ? artist : artist?.name))
      .filter(Boolean)
      .join(", ");
  }
  return track?.artists || "Unknown";
}

export function buildExportFilename(track, format, pattern = "artist-title") {
  const artist = artistName(track);
  const title = track?.title || "Song";
  const baseName =
    pattern === "title"
      ? title
      : pattern === "title-artist"
        ? `${title} - ${artist}`
        : `${artist} - ${title}`;
  return `${baseName}.${format === "mp3" ? "mp3" : "opus"}`;
}

export function joinExportPath(directory, filename) {
  if (!directory) return filename;
  const separator = directory.includes("\\") && !directory.includes("/") ? "\\" : "/";
  return `${directory.replace(/[\\/]+$/, "")}${separator}${filename}`;
}

// GTK save dialogs do not add the filter's extension, and the backend only writes audio files.
export function withExportExtension(path, format) {
  if (format === "mp3") return /\.mp3$/i.test(path) ? path : `${path}.mp3`;
  return /\.(opus|webm)$/i.test(path) ? path : `${path}.opus`;
}

export function shouldRememberExportDirectory(storage) {
  return storage.getItem(REMEMBER_EXPORT_DIRECTORY_KEY) !== "false";
}

export function storedFilenamePattern(storage) {
  const pattern = storage.getItem(EXPORT_FILENAME_PATTERN_KEY);
  return EXPORT_FILENAME_PATTERNS.has(pattern) ? pattern : "artist-title";
}
