export const SYSTEM_MIX_COLLECTION_IDS = Object.freeze({
  likedSongs: "kodama.system.liked-songs",
  history: "kodama.system.history",
  allSongs: "kodama.system.all-songs",
});

export function resolveMixCollectionId({ playlistId, isAlbum, mixCollectionId }) {
  if (typeof mixCollectionId === "string" && mixCollectionId.trim()) {
    return mixCollectionId.trim();
  }
  if (!isAlbum && typeof playlistId === "string" && playlistId.trim()) {
    return playlistId.trim();
  }
  return null;
}
