import { useState } from "react";
import AudioPanel from "./components/AudioPanel.jsx";
import { SLEEP_STATES } from "./lib/audio/constants.js";

// Dev 2 replaces `state` with the live value from the telemetry WebSocket context.
// Until then, this dropdown fakes the telemetry stream for testing.
export default function App() {
  const [state, setState] = useState("ASLEEP");

  return (
    <main className="app">
      <h1>CradleEcho</h1>

      <section className="card">
        <div className="row">
          <h2>Simulated state</h2>
          <select value={state} onChange={(e) => setState(e.target.value)}>
            {SLEEP_STATES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <p className="muted">Test-only stand-in for the telemetry stream.</p>
      </section>

      <AudioPanel state={state} />

      <p className="muted">
        CradleEcho is an informational wellness monitor, not a medical or SIDS-prevention device.
      </p>
    </main>
  );
}
