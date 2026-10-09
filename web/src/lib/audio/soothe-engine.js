import { createHeartbeatWavUrl } from "./ambient.js";

const FADE_TICK_MS = 100;

/**
 * Auto-soothe orchestrator (Tasks 3.3 + 3.4). Framework-agnostic.
 * Feed it telemetry via onTelemetry({ state }); read status via subscribe/getSnapshot.
 *
 * status: "idle" | "pending" | "soothing" | "fading"
 * events (options.onEvent): { type: "started" | "settled" | "stopped", at, snippet? }
 */
export class SootheEngine {
  constructor(options = {}) {
    this.opts = {
      triggerDelayMs: 4000, // RESTLESS must persist this long
      fadeMs: 8000, // ramp to silence after ASLEEP
      cooldownMs: 10 * 60 * 1000, // lockout after an intervention
      voiceVolume: 0.7,
      ambientVolume: 0.35,
      voiceRepeatMs: 20000, // gap between repeated phrases while still soothing
      ...options,
    };
    this.ownsAmbientUrl = !options.ambientUrl;
    this.ambientUrl = options.ambientUrl ?? createHeartbeatWavUrl();

    this.ambient = null;
    this.voice = null;
    this.snippets = [];
    this.nextSnippet = 0;

    this.enabled = true;
    this.status = "idle";
    this.cooldownUntil = 0;
    this.snippet = null;
    this.level = 1; // master gain, ramped during fade

    this.pendingTimer = null;
    this.fadeTimer = null;
    this.repeatTimer = null;
    this.lastState = null;
    this.listeners = new Set();
    this.cached = this.build();
  }

  // ---- public API -------------------------------------------------------

  subscribe = (fn) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = () => this.cached;

  setSnippets(snippets) {
    this.snippets = snippets;
    this.nextSnippet = 0;
  }

  /** Call from a user gesture so browsers allow later programmatic playback. */
  async unlock() {
    this.ensureElements();
    for (const el of [this.ambient, this.voice]) {
      if (!el) continue;
      const prev = el.volume;
      el.volume = 0;
      try {
        await el.play();
      } catch {
        /* still locked; retry on next gesture */
      }
      el.pause();
      el.currentTime = 0;
      el.volume = prev;
    }
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (!enabled) this.stop(false);
    else this.emit();
  }

  /** Feed every telemetry packet (or just { state }) here. */
  onTelemetry({ state }) {
    if (state === this.lastState) return;
    this.lastState = state;

    if (state === "RESTLESS") {
      this.onRestless();
    } else {
      this.cancelPending();
      if (state === "ASLEEP" && (this.status === "soothing" || this.status === "fading")) {
        this.beginFade();
      }
    }
  }

  /** Task 3.4 — instant mute. Stops all audio and starts the cooldown lockout. */
  stop(lockout = true) {
    const wasActive = this.status === "soothing" || this.status === "fading";
    this.cancelPending();
    this.halt();
    if (lockout) this.cooldownUntil = Date.now() + this.opts.cooldownMs;
    if (wasActive) this.opts.onEvent?.({ type: "stopped", at: Date.now() });
    this.setStatus("idle");
  }

  /** Clears the lockout (useful between demo runs). */
  resetCooldown() {
    this.cooldownUntil = 0;
    this.emit();
  }

  /** Plays a one-off clip immediately, e.g. "Talk to baby". Not subject to cooldown. */
  async playOnce(url) {
    const el = new Audio(url);
    el.volume = this.opts.voiceVolume;
    await el.play();
  }

  destroy() {
    this.stop(false);
    this.listeners.clear();
    // The ambient blob URL is intentionally not revoked: StrictMode's dev remount reuses this engine.
  }

  // ---- internals --------------------------------------------------------

  onRestless() {
    if (!this.enabled) return;
    // Restless again while fading out: bring the sound back instead of restarting.
    if (this.status === "fading") {
      this.clearFade();
      this.level = 1;
      this.applyVolumes();
      this.setStatus("soothing");
      return;
    }
    if (this.status !== "idle") return;

    this.setStatus("pending");
    this.pendingTimer = setTimeout(() => {
      this.pendingTimer = null;
      if (Date.now() < this.cooldownUntil) {
        this.setStatus("idle"); // locked out
        return;
      }
      this.start();
    }, this.opts.triggerDelayMs);
  }

  start() {
    this.ensureElements();
    this.level = 1;
    this.cooldownUntil = Date.now() + this.opts.cooldownMs;
    this.applyVolumes();

    this.ambient?.play().catch(() => {});
    this.playNextSnippet();
    if (this.opts.voiceRepeatMs > 0) {
      this.repeatTimer = setInterval(() => this.playNextSnippet(), this.opts.voiceRepeatMs);
    }

    this.opts.onEvent?.({ type: "started", at: Date.now(), snippet: this.snippet });
    this.setStatus("soothing");
  }

  playNextSnippet() {
    if (!this.voice || this.snippets.length === 0) return;
    const s = this.snippets[this.nextSnippet % this.snippets.length];
    this.nextSnippet++;
    this.snippet = s.text;
    this.voice.src = s.url;
    this.voice.play().catch(() => {});
    this.emit();
  }

  beginFade() {
    this.clearRepeat(); // let the current phrase finish, queue no more
    this.clearFade();
    this.setStatus("fading");
    const startLevel = this.level;
    const startedAt = Date.now();
    this.fadeTimer = setInterval(() => {
      const t = Math.min(1, (Date.now() - startedAt) / this.opts.fadeMs);
      this.level = startLevel * (1 - t);
      this.applyVolumes();
      if (t >= 1) {
        this.halt();
        this.opts.onEvent?.({ type: "settled", at: Date.now() });
        this.setStatus("idle");
      }
    }, FADE_TICK_MS);
  }

  applyVolumes() {
    const clamp = (v) => Math.max(0, Math.min(1, v));
    if (this.ambient) this.ambient.volume = clamp(this.opts.ambientVolume * this.level);
    if (this.voice) this.voice.volume = clamp(this.opts.voiceVolume * this.level);
  }

  halt() {
    this.clearFade();
    this.clearRepeat();
    for (const el of [this.ambient, this.voice]) {
      if (!el) continue;
      el.pause();
      el.currentTime = 0;
    }
    this.level = 1;
  }

  ensureElements() {
    if (typeof Audio === "undefined") return;
    if (!this.ambient) {
      this.ambient = new Audio(this.ambientUrl);
      this.ambient.loop = true;
    }
    if (!this.voice) this.voice = new Audio();
    this.applyVolumes();
  }

  cancelPending() {
    if (this.pendingTimer) clearTimeout(this.pendingTimer);
    this.pendingTimer = null;
    if (this.status === "pending") this.setStatus("idle");
  }

  clearFade() {
    if (this.fadeTimer) clearInterval(this.fadeTimer);
    this.fadeTimer = null;
  }

  clearRepeat() {
    if (this.repeatTimer) clearInterval(this.repeatTimer);
    this.repeatTimer = null;
  }

  setStatus(s) {
    this.status = s;
    this.emit();
  }

  build() {
    return {
      enabled: this.enabled,
      status: this.status,
      cooldownUntil: this.cooldownUntil,
      snippet: this.snippet,
    };
  }

  emit() {
    this.cached = this.build();
    this.listeners.forEach((l) => l());
  }
}
