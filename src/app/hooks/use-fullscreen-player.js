import { useCallback, useEffect, useRef, useState } from "react";
import { isNativeRuntime, native } from "@/shared/api/tauri.js";
import { createFullscreenIdle } from "./fullscreen-idle.js";

export function useFullscreenPlayer() {
  const [fullscreen, setFullscreen] = useState(false);
  const [visible, setVisible] = useState(true);
  const fullscreenRef = useRef(false);
  const pendingRef = useRef(false);
  const idleRef = useRef(null);
  const playerBarRef = useRef(null);

  const toggleFullscreen = useCallback(async () => {
    if (pendingRef.current) return null;
    pendingRef.current = true;
    const next = !fullscreenRef.current;
    try {
      if (isNativeRuntime()) await native.setFullscreen(next);
      fullscreenRef.current = next;
      setVisible(true);
      setFullscreen(next);
      return next;
    } catch (error) {
      console.error("Fullscreen transition failed", error);
      return null;
    } finally {
      pendingRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!fullscreen) return;
    const idle = createFullscreenIdle(setVisible);
    idleRef.current = idle;
    // Entering fullscreen can leave a stationary pointer already over the bar.
    if (playerBarRef.current?.matches(":hover")) idle.setHovered(true);
    window.addEventListener("mousemove", idle.onActivity);
    window.addEventListener("mousedown", idle.onActivity);
    return () => {
      idle.stop();
      idleRef.current = null;
      window.removeEventListener("mousemove", idle.onActivity);
      window.removeEventListener("mousedown", idle.onActivity);
    };
  }, [fullscreen]);

  useEffect(() => {
    document.documentElement.classList.toggle("cursor-hidden", fullscreen && !visible);
    return () => document.documentElement.classList.remove("cursor-hidden");
  }, [fullscreen, visible]);

  return {
    fullscreen,
    playerVisible: !fullscreen || visible,
    toggleFullscreen,
    playerBarProps: {
      ref: playerBarRef,
      onMouseEnter: () => idleRef.current?.setHovered(true),
      onMouseLeave: () => idleRef.current?.setHovered(false),
    },
  };
}
