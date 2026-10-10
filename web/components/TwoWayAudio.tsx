"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { talkWsUrl, listenWsUrl, audioCapabilitiesUrl } from "@/lib/config";
import { float32ToInt16, resampleTo16kHz } from "@/lib/audio/pcm";
import { SootheEngine } from "@/lib/audio/soothe-engine";

type TalkState = "idle" | "connecting" | "talking" | "busy" | "error";
type ListenState = "off" | "connecting" | "listening" | "error";

interface AudioCapabilities {
  talk: boolean;
  listen: boolean;
}

const JITTER_TARGET_MS = 150;
const JITTER_MAX_MS = 500;
const TARGET_SAMPLE_RATE = 16000;

function useSecureContext(): boolean {
  return useState(() => (typeof window !== "undefined" ? window.isSecureContext : true))[0];
}

export function TwoWayAudio({ sootheEngine }: { sootheEngine: SootheEngine | null }) {
  const secureContext = useSecureContext();
  const [capabilities, setCapabilities] = useState<AudioCapabilities | null>(null);
  const [talkState, setTalkState] = useState<TalkState>("idle");
  const [talkError, setTalkError] = useState<string | null>(null);
  const [listenState, setListenState] = useState<ListenState>("off");
  const [listenError, setListenError] = useState<string | null>(null);
  const [listenLevel, setListenLevel] = useState(0);

  const talkWsRef = useRef<WebSocket | null>(null);
  const listenWsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const listenContextRef = useRef<AudioContext | null>(null);
  const listenBufferRef = useRef<Float32Array[]>([]);
  const listenPlayingRef = useRef(false);
  const listenGainRef = useRef<GainNode | null>(null);

  useEffect(() => {
    async function fetchCaps() {
      try {
        const res = await fetch(audioCapabilitiesUrl());
        if (res.ok) {
          const data = await res.json();
          setCapabilities(data);
        }
      } catch {
        setCapabilities({ talk: false, listen: false });
      }
    }
    fetchCaps();
  }, []);

  const cleanupTalk = useCallback(() => {
    if (talkWsRef.current) {
      talkWsRef.current.onclose = null;
      talkWsRef.current.close();
      talkWsRef.current = null;
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setTalkState("idle");
    setTalkError(null);
    if (sootheEngine) sootheEngine.setEnabled(true);
  }, [sootheEngine]);

  const startTalking = useCallback(async () => {
    if (talkState !== "idle") return;
    if (!capabilities?.talk) {
      setTalkError("Talk is not supported on this monitor");
      setTalkState("error");
      return;
    }
    if (!secureContext) {
      setTalkError("Microphone needs HTTPS or localhost");
      setTalkState("error");
      return;
    }

    setTalkState("connecting");
    setTalkError(null);
    if (sootheEngine) sootheEngine.setEnabled(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      mediaStreamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
      audioContextRef.current = ctx;
      await ctx.audioWorklet.addModule("/pcm-worklet.js");

      const source = ctx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      const worklet = new AudioWorkletNode(ctx, "pcm-worklet");
      workletNodeRef.current = worklet;
      source.connect(worklet).connect(ctx.destination);

      worklet.port.onmessage = (e) => {
        if (talkWsRef.current?.readyState === WebSocket.OPEN) {
          const float32 = e.data as Float32Array;
          const resampled = resampleTo16kHz(float32, ctx.sampleRate);
          const int16 = float32ToInt16(resampled);
          talkWsRef.current.send(int16.buffer);
        }
      };

      const ws = new WebSocket(talkWsUrl());
      talkWsRef.current = ws;
      ws.binaryType = "arraybuffer";

      ws.onopen = () => setTalkState("talking");
      ws.onclose = (e) => {
        if (e.code === 4409) setTalkError("Another parent is talking");
        else if (e.code !== 1000) setTalkError(`Disconnected (code ${e.code})`);
        cleanupTalk();
      };
      ws.onerror = () => ws.close();
    } catch (err) {
      console.error("Talk error:", err);
      setTalkError("Could not start microphone");
      setTalkState("error");
      if (sootheEngine) sootheEngine.setEnabled(true);
    }
  }, [talkState, capabilities, secureContext, sootheEngine, cleanupTalk]);

  const stopTalking = useCallback(() => {
    cleanupTalk();
  }, [cleanupTalk]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.nativeEvent.pointerId);
    startTalking();
  }, [startTalking]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    e.currentTarget.releasePointerCapture(e.nativeEvent.pointerId);
    stopTalking();
  }, [stopTalking]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.key === " " || e.key === "Enter") && !e.repeat) {
        e.preventDefault();
        startTalking();
      }
    },
    [startTalking],
  );

  const handleKeyUp = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        stopTalking();
      }
    },
    [stopTalking],
  );

  const handleBlur = useCallback(() => {
    if (talkState === "talking" || talkState === "connecting") stopTalking();
  }, [talkState, stopTalking]);

  const handleVisibilityChange = useCallback(() => {
    if (document.visibilityState === "hidden" && (talkState === "talking" || talkState === "connecting")) {
      stopTalking();
    }
  }, [talkState, stopTalking]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [handleKeyDown, handleKeyUp, handleVisibilityChange]);

  const scheduleListenPlayback = useCallback(() => {
    const ctx = listenContextRef.current;
    const buffer = listenBufferRef.current;
    const gain = listenGainRef.current;
    if (!ctx || !gain || buffer.length === 0 || listenPlayingRef.current) return;

    listenPlayingRef.current = true;
    const playNext = () => {
      if (buffer.length === 0) {
        listenPlayingRef.current = false;
        return;
      }
      const chunk = buffer.shift()!;
      const now = ctx.currentTime;
      const source = ctx.createBufferSource();
      const audioBuffer = ctx.createBuffer(1, chunk.length, TARGET_SAMPLE_RATE);
      audioBuffer.getChannelData(0).set(chunk);
      source.buffer = audioBuffer;
      source.connect(gain);
      source.start(now);
      source.onended = () => {
        const bufferedMs = buffer.reduce((sum, c) => sum + (c.length / TARGET_SAMPLE_RATE) * 1000, 0);
        if (bufferedMs > JITTER_MAX_MS) {
          const dropCount = Math.ceil((bufferedMs - JITTER_TARGET_MS) / (JITTER_TARGET_MS / buffer.length));
          buffer.splice(0, Math.min(dropCount, buffer.length));
        }
        playNext();
      };
    };
    playNext();
  }, []);

  const startListening = useCallback(async () => {
    if (listenState !== "off") return;
    if (!capabilities?.listen) {
      setListenError("Listening is not supported on this monitor");
      setListenState("error");
      return;
    }

    setListenState("connecting");
    setListenError(null);

    try {
      const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
      listenContextRef.current = ctx;
      const gain = ctx.createGain();
      gain.connect(ctx.destination);
      listenGainRef.current = gain;

      const ws = new WebSocket(listenWsUrl());
      listenWsRef.current = ws;
      ws.binaryType = "arraybuffer";

      ws.onopen = () => setListenState("listening");
      ws.onmessage = (e) => {
        const int16 = new Int16Array(e.data);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
          float32[i] = int16[i] < 0 ? int16[i] / 0x8000 : int16[i] / 0x7fff;
        }
        const resampled = resampleTo16kHz(float32, TARGET_SAMPLE_RATE);
        listenBufferRef.current.push(resampled);

        let sum = 0;
        for (let i = 0; i < resampled.length; i++) sum += resampled[i] * resampled[i];
        const rms = Math.sqrt(sum / resampled.length);
        setListenLevel(Math.min(1, rms * 10));

        scheduleListenPlayback();
      };
      ws.onclose = (e) => {
        if (e.code === 4403) setListenError("Listening is turned off on this monitor");
        else if (e.code !== 1000) setListenError(`Disconnected (code ${e.code})`);
        setListenState("off");
        if (listenContextRef.current) {
          listenContextRef.current.close().catch(() => {});
          listenContextRef.current = null;
        }
        listenBufferRef.current = [];
        listenGainRef.current = null;
        setListenLevel(0);
      };
      ws.onerror = () => ws.close();
    } catch (err) {
      console.error("Listen error:", err);
      setListenError("Could not start listening");
      setListenState("error");
    }
  }, [listenState, capabilities, scheduleListenPlayback]);

  const stopListening = useCallback(() => {
    if (listenWsRef.current) {
      listenWsRef.current.close();
      listenWsRef.current = null;
    }
    if (listenContextRef.current) {
      listenContextRef.current.close().catch(() => {});
      listenContextRef.current = null;
    }
    listenBufferRef.current = [];
    listenGainRef.current = null;
    setListenState("off");
    setListenError(null);
    setListenLevel(0);
  }, []);

  const toggleListen = useCallback(() => {
    if (listenState === "off" || listenState === "error") startListening();
    else stopListening();
  }, [listenState, startListening, stopListening]);

  if (!capabilities) return null;
  if (!capabilities.talk && !capabilities.listen) return null;

  const talkLabel =
    talkState === "idle"
      ? "Hold to talk"
      : talkState === "connecting"
        ? "Connecting…"
        : talkState === "talking"
          ? "Talking… release to stop"
          : talkState === "busy"
            ? "Another parent is talking"
            : "Error";

  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">Two-way Audio</h2>

      {capabilities.talk && (
        <div className="flex flex-col gap-3">
          {!secureContext ? (
            <div className="rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-300 ring-1 ring-amber-500/30">
              <div>Microphone needs HTTPS or localhost</div>
              <a href={`http://${typeof window !== "undefined" ? window.location.hostname : "localhost"}/pair`} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-xs underline hover:text-amber-100">
                Pair this device to enable the microphone
              </a>
            </div>
          ) : (
            <button
              type="button"
              onPointerDown={handlePointerDown}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              onPointerLeave={handlePointerUp}
              onBlur={handleBlur}
              disabled={talkState !== "idle" && talkState !== "talking"}
              className={`
                relative flex items-center justify-center gap-3 rounded-xl px-5 py-4 text-sm font-medium transition
                ${talkState === "talking" ? "bg-tone/20 text-tone ring-2 ring-tone" : "bg-white/5 text-ink ring-1 ring-white/10 hover:bg-white/10"}
                ${talkState === "busy" || talkState === "error" ? "cursor-not-allowed opacity-60" : ""}
                ${talkState === "connecting" ? "animate-pulse" : ""}
              `}
              aria-pressed={talkState === "talking"}
              aria-label={talkLabel}
            >
              <svg className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              <span>{talkLabel}</span>
              {talkState === "talking" && (
                <span className="breathe h-2 w-2 rounded-full bg-tone" aria-hidden />
              )}
            </button>
          )}
          {talkError && (
            <p className="text-sm text-rose-300" role="alert">{talkError}</p>
          )}
        </div>
      )}

      {capabilities.listen && (
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={listenState === "listening" || listenState === "connecting"}
              onChange={toggleListen}
              disabled={listenState === "connecting"}
              className="h-4 w-4 rounded border-white/20 bg-white/5 text-tone focus:ring-2 focus:ring-tone/50"
            />
            <span className="text-sm text-ink">{listenState === "listening" ? "Stop listening" : "Listen to nursery"}</span>
            {listenState === "connecting" && <span className="breathe h-2 w-2 rounded-full bg-tone" aria-hidden />}
          </label>
          {(listenState === "listening" || listenState === "connecting") && (
            <div className="flex items-center gap-3 text-sm text-ink-dim">
              <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full bg-tone transition-all duration-100"
                  style={{ width: `${listenLevel * 100}%` }}
                  aria-hidden
                />
              </div>
              <span className="tabular-nums w-12 text-right">{Math.round(listenLevel * 100)}%</span>
            </div>
          )}
          {listenError && (
            <p className="text-sm text-rose-300" role="alert">{listenError}</p>
          )}
        </div>
      )}

      <p className="text-xs text-ink-faint">
        Audio is streamed directly between this browser and the monitor. No audio is recorded or stored.
      </p>
    </section>
  );
}