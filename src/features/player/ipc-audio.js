import { native, nativeCommand } from "@/shared/api/tauri.js";

export class IpcAudio {
  constructor() {
    this._src = "";
    this._srcDirty = false; // true when src was set but play() not called yet
    this._pendingSeekTo = 0; // seek target to use on the next play() call
    this._currentTime = 0;
    this._duration = 0;
    this._paused = true;
    this._volume = 0.16; // same default as Rust thread (0.4² quadratic)
    this._listeners = {};
    // Fallback: if Rust commands don't exist (binary not recompiled),
    // _fallback is set to a plain HTMLAudioElement and all calls route there.
    this._fallback = null; // null = not decided, false = Rust works, Audio = fallback
    this._probePromise = null; // dedup the one-time probe
    this._e2eMedia = globalThis.__kodamaE2e?.media;

    // Probe immediately to determine whether the native audio commands exist.
    if (!this._e2eMedia) {
      this._probe();
    } else {
      this._fallback = false;
      this._probePromise = Promise.resolve();
    }
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen("audio-progress", ({ payload }) => {
        if (this._fallback) return; // ignore Rust events when in fallback mode
        this._currentTime = payload.position;
        if (payload.duration > 0) this._duration = payload.duration;
        if (payload.paused !== this._paused) this._paused = payload.paused;
        this._fire("timeupdate");
      });
      listen("playback-track-changed", ({ payload }) => {
        if (this._fallback || !payload?.track?.videoId) return;
        // Progress events arrive independently from selection changes. Clear the outgoing
        // track's clock as soon as native playback commits a new track so consumers such as
        // synced lyrics cannot render the new song at the old song's timestamp while waiting
        // for its first audio-progress event.
        this._currentTime = 0;
        this._duration = 0;
        // The new source may still be loading. Do not let consumers interpolate from zero
        // during that gap; audio-progress marks this false only once native playback reports
        // the new source's actual transport state.
        this._paused = true;
        this._fire("pause");
        this._fire("timeupdate");
      });
      listen("audio-ended", () => {
        if (this._fallback) return;
        this._paused = true;
        this._fire("ended");
      });
      listen("audio-loaded", ({ payload }) => {
        if (this._fallback) return;
        if (payload.duration > 0) this._duration = payload.duration;
        this._fire("loadedmetadata");
        this._fire("canplay");
      });
      listen("audio-error", ({ payload }) => {
        if (this._fallback) return;
        console.error("[IpcAudio] Rust decode error:", payload);
        this._fire("error");
      });
    });
  }

  // ── Fallback probe ──────────────────────────────────────────────────────────
  // Calls audio_set_volume (side-effect-free) to check if the Rust command
  // exists.  If it fails with "unknown command", switch to HTML5 Audio.
  _probe() {
    if (this._probePromise) return this._probePromise;
    // Use audio_pause as a harmless no-op probe — it does nothing when no song
    // is playing, and importantly does NOT touch volume state.
    this._probePromise = native
      .audioPause()
      .then(() => {
        this._fallback = false;
        console.log("[IpcAudio] Rust audio commands available ✓");
        // Now sync the stored volume to Rust so it's ready for first play
        native.setAudioVolume(this._volume);
      })
      .catch(() => {
        console.warn("[IpcAudio] Rust audio commands not found — falling back to HTML5 Audio");
        this._fallback = this._createFallbackAudio();
        if (this._src) this._fallback.src = this._src;
        this._fallback.volume = this._volume;
      });
    return this._probePromise;
  }

  _createFallbackAudio() {
    const a = new Audio();
    // Wire native events → our listener system
    for (const evt of [
      "timeupdate",
      "ended",
      "loadedmetadata",
      "canplay",
      "error",
      "volumechange",
    ]) {
      a.addEventListener(evt, () => this._fire(evt));
    }
    return a;
  }

  // ── Private helpers ────────────────────────────────────────────────────────
  _cmd(command) {
    if (this._e2eMedia) {
      // Browser E2E owns its own media command recorder.
      this._e2eMedia.record(command.name, command.args || {});
      return Promise.resolve();
    }
    if (this._fallback) return Promise.resolve(); // Rust path disabled
    console.log(
      "[IpcAudio] →",
      command.name,
      command.args?.url ? command.args.url.substring(0, 80) + "…" : ""
    );
    command.call().catch((e) => console.error("[IpcAudio] ERROR", command.name, e));
    return Promise.resolve();
  }

  _fire(type) {
    (this._listeners[type] || []).forEach((h) => {
      try {
        h({ type });
      } catch (e) {
        console.error(e);
      }
    });
  }

  // ── HTMLAudioElement-compatible API ────────────────────────────────────────
  // _fb() returns the fallback Audio if active, or false/null.
  // null = probe still running (undecided), false = Rust is active, Audio = fallback
  get _fb() {
    return this._fallback;
  }

  get src() {
    return this._fb ? this._fb.src : this._src;
  }
  set src(url) {
    // Always store locally so we can replay onto fallback if probe hasn't finished
    this._src = url;
    this._srcDirty = true;
    this._pendingSeekTo = 0;
    // The Rust path only updates position from incoming progress events. Reset it immediately so
    // controls cannot read the previous track's position while the new source is still loading.
    this._currentTime = 0;
    this._duration = 0;
    if (this._fb) {
      this._fb.src = url;
    } else if (this._fb === null && this._probePromise) {
      // Probe still running — queue replay
      this._probePromise.then(() => {
        if (this._fb) this._fb.src = url;
      });
    }
  }

  get currentTime() {
    return this._fb ? this._fb.currentTime : this._currentTime;
  }
  set currentTime(t) {
    if (this._fb) {
      this._fb.currentTime = t;
      return;
    }
    this._currentTime = t;
    if (this._srcDirty) {
      this._pendingSeekTo = t;
    } else {
      this._cmd({
        name: nativeCommand.audioSeek,
        args: { position: t },
        call: () => native.audioSeek(t),
      });
    }
  }

  get duration() {
    return this._fb ? this._fb.duration : this._duration;
  }
  get paused() {
    return this._fb ? this._fb.paused : this._paused;
  }

  get volume() {
    return this._fb ? this._fb.volume : this._volume;
  }
  set volume(v) {
    this._volume = v; // always store for probe replay
    if (this._fb) {
      this._fb.volume = v;
      this._fire("volumechange");
      return;
    }
    this._cmd({
      name: nativeCommand.setAudioVolume,
      args: { volume: v },
      call: () => native.setAudioVolume(v),
    });
    this._fire("volumechange");
  }

  play() {
    // If probe hasn't resolved yet, wait for it then play
    if (this._fallback === null && this._probePromise) {
      return this._probePromise.then(() => this.play());
    }
    if (this._fb) return this._fb.play();
    if (this._srcDirty && this._src) {
      this._srcDirty = false;
      const seekTo = this._pendingSeekTo;
      this._pendingSeekTo = 0;
      this._paused = false;
      console.log("[IpcAudio] play() → audio_play (new src)");
      this._cmd({
        name: nativeCommand.audioPlay,
        args: { url: this._src, seekTo },
        call: () => native.audioPlay(this._src, seekTo),
      });
    } else {
      this._paused = false;
      console.log("[IpcAudio] play() → audio_resume");
      this._cmd({ name: nativeCommand.audioResume, call: native.audioResume });
    }
    return Promise.resolve();
  }

  pause() {
    if (this._fb) {
      this._fb.pause();
      return;
    }
    this._paused = true;
    this._cmd({ name: nativeCommand.audioPause, call: native.audioPause });
  }

  addEventListener(type, handler) {
    if (!this._listeners[type]) this._listeners[type] = [];
    this._listeners[type].push(handler);
  }

  removeEventListener(type, handler) {
    if (!this._listeners[type]) return;
    this._listeners[type] = this._listeners[type].filter((h) => h !== handler);
  }
}
