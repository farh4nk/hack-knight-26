import { useEffect, useState } from "react";

const LABELS = {
  idle: "Auto-soothe ready",
  pending: "Restlessness detected…",
  soothing: "Soothing in your voice",
  fading: "Settled — fading out",
};

export default function SootheControls({ engine, snapshot, onChangeVoice }) {
  const [now, setNow] = useState(() => Date.now());
  const locked = snapshot.cooldownUntil > now;
  const active = snapshot.status === "soothing" || snapshot.status === "fading";

  useEffect(() => {
    if (!locked) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [locked]);

  const minsLeft = Math.ceil((snapshot.cooldownUntil - now) / 60000);

  return (
    <section className="card">
      <div className="row">
        <h2>Auto-soothe</h2>
        <label>
          <input
            type="checkbox"
            checked={snapshot.enabled}
            onChange={(e) => {
              // The click is a user gesture, so also unlock audio playback.
              if (e.target.checked) engine.unlock();
              engine.setEnabled(e.target.checked);
            }}
          />{" "}
          On
        </label>
      </div>

      <p role="status" className="muted">
        {snapshot.enabled ? LABELS[snapshot.status] : "Auto-soothe is off"}
        {snapshot.snippet && active ? ` — “${snapshot.snippet}”` : ""}
      </p>

      {locked && !active && (
        <p className="muted">
          Paused for about {minsLeft} min so it doesn’t repeat.{" "}
          <button type="button" className="link" onClick={() => engine.resetCooldown()}>
            Reset
          </button>
        </p>
      )}

      <button
        type="button"
        className="danger"
        onClick={() => engine.stop()}
        disabled={!active && snapshot.status !== "pending"}
      >
        Mute / Stop Soothe
      </button>

      {onChangeVoice && (
        <button type="button" className="link muted" onClick={onChangeVoice}>
          Re-record my voice
        </button>
      )}
    </section>
  );
}
