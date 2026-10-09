import { createHeartbeatWavUrl } from "./ambient";
import { SoothingSnippet } from "./elevenlabs";

const FADE_TICK_MS = 100;

export type SootheStatus = "idle" | "pending" | "soothing" | "fading";

export interface SootheEvent {
  type: "started" | "settled" | "stopped";
  at: number;
  snippet?: string | null;
}

export interface SootheEngineOptions {
  triggerDelayMs?: number; // default 4000
  fadeMs?: number; // default 8000
  cooldownMs?: number; // default 10 * 60 * 1000
  voiceVolume?: number; // default 0.7
  ambientVolume?: number; // default 0.35
  voiceRepeatMs?: number; // default 20000
  ambientUrl?: string;
  onEvent?: (event: SootheEvent) => void;
}

export interface SootheSnapshot {
  enabled: boolean;
  status: SootheStatus;
  cooldownUntil: number;
  snippet: string | null;
}

/**
 * Auto-soothe orchestrator (Tasks 3.3 + 3.4).
 * Monitors telemetry state; plays heartbeat + cloned voice snippet, ramps down smoothly on ASLEEP.
 */
export class SootheEngine {
  opts: Required<SootheEngineOptions>;
  ambientUrl: string;
  ambient: HTMLAudioElement | null = null;
  voice: HTMLAudioElement | null = null;
  snippets: SoothingSnippet[] = [];
  nextSnippet = 0;

  enabled = true;
  status: SootheStatus = "idle";
  cooldownUntil = 0;
  snippet: string | null = null;
  level = 1;

  pendingTimer: ReturnType<typeof setTimeout> | null = null;
  fadeTimer: ReturnType<typeof setInterval> | null = null;
  repeatTimer: ReturnType<typeof setInterval> | null = null;
  lastState: string | null = null;
  listeners = new Set<() => void>();
  cached: SootheSnapshot;

  constructor(options: SootheEngineOptions = {}) {
    this.opts = {
      triggerDelayMs: 4000,
      fadeMs: 8000,
      cooldownMs: 10 * 60 * 1000,
      voiceVolume: 0.7,
      ambientVolume: 0.35,
      voiceRepeatMs: 20000,
      ambientUrl: options.ambientUrl ?? "",
      onEvent: () => {},
      ...options,
    };

    this.ambientUrl = this.opts.ambientUrl || (typeof window !== "undefined" ? createHeartbeatWavUrl() : "");
    this.cached = this.build();
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = (): SootheSnapshot => this.cached;

  setSnippets(snippets: SoothingSnippet[]) {
    this.snippets = snippets;
    this.nextSnippet = 0;
  }

  async unlock() {
    if (typeof window === "undefined") return;
    this.ensureElements();
    for (const el of [this.ambient, this.voice]) {
      if (!el) continue;
      const prev = el.volume;
      el.volume = 0;
      try {
        await el.play();
      } catch {
        /* unlock on next user click */
      }
      el.pause();
      el.currentTime = 0;
      el.volume = prev;
    }
  }

  setEnabled(enabled: boolean) {
    this.enabled = enabled;
    if (!enabled) this.stop(false);
    else this.emit();
  }

  onTelemetry({ state }: { state?: string | null }) {
    if (!state || state === this.lastState) return;
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

  stop(lockout = true) {
    const wasActive = this.status === "soothing" || this.status === "fading";
    this.cancelPending();
    this.halt();
    if (lockout) this.cooldownUntil = Date.now() + this.opts.cooldownMs;
    if (wasActive) this.opts.onEvent({ type: "stopped", at: Date.now() });
    this.setStatus("idle");
  }

  resetCooldown() {
    this.cooldownUntil = 0;
    this.emit();
  }

  async playOnce(url: string) {
    if (typeof window === "undefined") return;
    const el = new Audio(url);
    el.volume = this.opts.voiceVolume;
    await el.play();
  }

  destroy() {
    this.stop(false);
    this.listeners.clear();
  }

  private onRestless() {
    if (!this.enabled) return;
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
        this.setStatus("idle");
        return;
      }
      this.start();
    }, this.opts.triggerDelayMs);
  }

  private start() {
    this.ensureElements();
    this.level = 1;
    this.cooldownUntil = Date.now() + this.opts.cooldownMs;
    this.applyVolumes();

    this.ambient?.play().catch(() => {});
    this.playNextSnippet();
    if (this.opts.voiceRepeatMs > 0) {
      this.repeatTimer = setInterval(() => this.playNextSnippet(), this.opts.voiceRepeatMs);
    }

    this.opts.onEvent({ type: "started", at: Date.now(), snippet: this.snippet });
    this.setStatus("soothing");
  }

  private playNextSnippet() {
    if (!this.voice || this.snippets.length === 0) return;
    const s = this.snippets[this.nextSnippet % this.snippets.length];
    this.nextSnippet++;
    this.snippet = s.text;
    this.voice.src = s.url;
    this.voice.play().catch(() => {});
    this.emit();
  }

  private beginFade() {
    this.clearRepeat();
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
        this.opts.onEvent({ type: "settled", at: Date.now() });
        this.setStatus("idle");
      }
    }, FADE_TICK_MS);
  }

  private applyVolumes() {
    const clamp = (v: number) => Math.max(0, Math.min(1, v));
    if (this.ambient) this.ambient.volume = clamp(this.opts.ambientVolume * this.level);
    if (this.voice) this.voice.volume = clamp(this.opts.voiceVolume * this.level);
  }

  private halt() {
    this.clearFade();
    this.clearRepeat();
    for (const el of [this.ambient, this.voice]) {
      if (!el) continue;
      el.pause();
      el.currentTime = 0;
    }
    this.level = 1;
  }

  private ensureElements() {
    if (typeof window === "undefined" || typeof Audio === "undefined") return;
    if (!this.ambient) {
      if (!this.ambientUrl) this.ambientUrl = createHeartbeatWavUrl();
      this.ambient = new Audio(this.ambientUrl);
      this.ambient.loop = true;
    }
    if (!this.voice) this.voice = new Audio();
    this.applyVolumes();
  }

  private cancelPending() {
    if (this.pendingTimer) clearTimeout(this.pendingTimer);
    this.pendingTimer = null;
    if (this.status === "pending") this.setStatus("idle");
  }

  private clearFade() {
    if (this.fadeTimer) clearInterval(this.fadeTimer);
    this.fadeTimer = null;
  }

  private clearRepeat() {
    if (this.repeatTimer) clearInterval(this.repeatTimer);
    this.repeatTimer = null;
  }

  private setStatus(s: SootheStatus) {
    this.status = s;
    this.emit();
  }

  private build(): SootheSnapshot {
    return {
      enabled: this.enabled,
      status: this.status,
      cooldownUntil: this.cooldownUntil,
      snippet: this.snippet,
    };
  }

  private emit() {
    this.cached = this.build();
    this.listeners.forEach((l) => l());
  }
}
