import { useAutoSoothe } from "../hooks/useAutoSoothe.js";
import { useVoiceProfile } from "../hooks/useVoiceProfile.js";
import SootheControls from "./SootheControls.jsx";
import VoiceRecorder from "./VoiceRecorder.jsx";

/**
 * Dev 3's drop-in panel. Render with the live state from the telemetry context:
 *   <AudioPanel state={telemetry?.state} />
 */
export default function AudioPanel({ state }) {
  const { voiceId, snippets, error, onboard, reset } = useVoiceProfile();
  const { engine, snapshot } = useAutoSoothe(state, snippets, {
    // Hook for the visible parent notification / Dev 4's soothe_events logging.
    onEvent: (e) => console.info("[auto-soothe]", e),
    // For quick testing: cooldownMs: 15000, fadeMs: 3000,
  });

  return (
    <>
      {!voiceId && <VoiceRecorder onComplete={onboard} />}
      {voiceId && snippets.length === 0 && !error && (
        <p className="muted">Preparing soothing phrases…</p>
      )}
      {error && <p role="alert" className="err">{error}</p>}
      {voiceId && <SootheControls engine={engine} snapshot={snapshot} onChangeVoice={reset} />}
    </>
  );
}
