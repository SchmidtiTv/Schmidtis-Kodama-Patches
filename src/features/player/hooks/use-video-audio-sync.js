import { useEffect, useRef } from "react";

async function loadAndSeek(audio, url, targetPosition, wasPlaying) {
  audio.src = url;
  await audio.play().catch((error) => console.error("[VideoSync] play error:", error));
  await new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      audio.removeEventListener("canplay", finish);
      resolve();
    };
    audio.addEventListener("canplay", finish);
    setTimeout(finish, 4000);
  });
  audio.currentTime = targetPosition;
  if (!wasPlaying) audio.pause();
}

export function useVideoAudioSync({
  enabled,
  audioRef,
  trackRef,
  fetchUrl,
  trackId,
  showVideoView,
  videoSync,
  setIsPlaying,
}) {
  const activeRef = useRef(false);
  const trackIdRef = useRef(null);
  const showVideoViewRef = useRef(showVideoView);
  const fetchUrlRef = useRef(fetchUrl);

  useEffect(() => {
    showVideoViewRef.current = showVideoView;
    fetchUrlRef.current = fetchUrl;
  }, [fetchUrl, showVideoView]);

  useEffect(() => {
    activeRef.current = false;
    trackIdRef.current = null;
  }, [trackId]);

  useEffect(() => {
    if (!enabled) {
      activeRef.current = false;
      trackIdRef.current = null;
      return;
    }
    const audio = audioRef.current;
    const current = trackRef.current;
    if (!audio || !current) return;
    const trackId = current.videoId;
    const wasPlaying = !audio.paused;
    let cancelled = false;

    if (showVideoView) {
      if (!videoSync?.ready || !videoSync.counterpartVideoId) return;
      if (videoSync.selfVideo) {
        activeRef.current = true;
        trackIdRef.current = trackId;
        return;
      }
      const targetPosition = Math.max(0, audio.currentTime + (videoSync.offsetSeconds || 0));
      fetchUrlRef.current(videoSync.counterpartVideoId).then(async (url) => {
        if (cancelled || !url || trackRef.current?.videoId !== trackId || !showVideoViewRef.current)
          return;
        activeRef.current = true;
        trackIdRef.current = trackId;
        await loadAndSeek(audio, url, targetPosition, wasPlaying);
        if (wasPlaying) setIsPlaying(true);
      });
    } else if (activeRef.current && trackIdRef.current === trackId) {
      if (videoSync?.selfVideo) {
        activeRef.current = false;
        trackIdRef.current = null;
        return;
      }
      const targetPosition = Math.max(0, audio.currentTime - (videoSync?.offsetSeconds || 0));
      fetchUrlRef.current(trackId).then(async (url) => {
        if (cancelled || !url || trackRef.current?.videoId !== trackId) return;
        activeRef.current = false;
        trackIdRef.current = null;
        await loadAndSeek(audio, url, targetPosition, wasPlaying);
        if (wasPlaying) setIsPlaying(true);
      });
    }

    return () => {
      cancelled = true;
    };
  }, [
    enabled,
    audioRef,
    trackRef,
    setIsPlaying,
    showVideoView,
    videoSync?.ready,
    videoSync?.counterpartVideoId,
    videoSync?.offsetSeconds,
    videoSync?.selfVideo,
  ]);
}
