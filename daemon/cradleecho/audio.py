"""Edge Audio Player for Raspberry Pi / Edge Daemon.

Enables the Raspberry Pi to play calming heartbeat soundscapes and
parent voice soothing audio directly through its connected speaker in the crib.
Uses `aplay` (ALSA standard on Linux/Pi) or `afplay` (macOS), with safe non-blocking execution.
"""

import base64
import logging
import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from typing import Optional

logger = logging.getLogger("cradleecho.audio")


def generate_soothing_chime_wav(duration_s: float = 4.0, sample_rate: int = 22050) -> bytes:
    """Generates a soothing 4-tone lullaby chime in 16-bit PCM mono WAV."""
    notes = [523.25, 659.25, 783.99, 1046.50]  # C5 - E5 - G5 - C6 arpeggio
    total_frames = int(sample_rate * duration_s)
    frames_per_note = total_frames // len(notes)

    samples = []
    for i in range(total_frames):
        note_idx = min(i // frames_per_note, len(notes) - 1)
        freq = notes[note_idx]
        note_phase = (i % frames_per_note) / frames_per_note
        # Gentle decaying envelope
        env = math.exp(-3.5 * note_phase)
        sine = math.sin(2.0 * math.pi * freq * (i / sample_rate))
        val = int(sine * env * 12000.0)
        samples.append(struct.pack("<h", max(-32768, min(32767, val))))

    raw_pcm = b"".join(samples)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            temp_path = tf.name
            with wave.open(tf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(raw_pcm)

        with open(temp_path, "rb") as f:
            return f.read()
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


class EdgeAudioPlayer:
    """Manages audio playback on the edge device hardware."""

    def __init__(self):
        self._current_proc: Optional[subprocess.Popen] = None
        self._playing = False
        self._player_bin = self._find_player_binary()
        if self._player_bin:
            logger.info("Found audio player binary: %s", self._player_bin)
        else:
            logger.warning("No audio player binary found (aplay/afplay missing). Edge audio simulated.")

    def _find_player_binary(self) -> Optional[str]:
        for candidate in ["aplay", "afplay", "ffplay", "mpg123"]:
            path = shutil.which(candidate)
            if path:
                return path
        return None

    @property
    def is_playing(self) -> bool:
        if self._current_proc is not None:
            if self._current_proc.poll() is None:
                return True
            self._current_proc = None
            self._playing = False
        return self._playing

    def play_wav_bytes(self, wav_bytes: bytes, loop: bool = False) -> bool:
        """Plays raw WAV bytes on the device speaker."""
        self.stop()

        if not self._player_bin:
            logger.info("[SIMULATED AUDIO] Edge speaker playing %d bytes (loop=%s)", len(wav_bytes), loop)
            self._playing = True
            return True

        try:
            # Write to temporary file for player process
            suffix = ".wav"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(wav_bytes)

            cmd = [self._player_bin]
            if "aplay" in self._player_bin:
                cmd.extend(["-q", tmp_path])
            elif "afplay" in self._player_bin:
                cmd.append(tmp_path)
            elif "ffplay" in self._player_bin:
                cmd.extend(["-nodisp", "-autoexit", tmp_path])
            else:
                cmd.append(tmp_path)

            self._current_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._playing = True
            logger.info("Playing audio on Pi hardware: pid=%s", self._current_proc.pid)
            return True
        except Exception as e:
            logger.error("Failed to play audio on Pi hardware: %s", e)
            return False

    def play_base64_or_default(self, audio_base64: Optional[str] = None) -> bool:
        """Plays base64-encoded audio payload or falls back to soothing chime."""
        if audio_base64:
            try:
                wav_bytes = base64.b64decode(audio_base64)
                return self.play_wav_bytes(wav_bytes)
            except Exception as e:
                logger.warning("Failed to decode base64 audio: %s; falling back to chime", e)

        # Default fallback calming sound
        chime = generate_soothing_chime_wav(duration_s=4.0)
        return self.play_wav_bytes(chime)

    def stop(self):
        """Immediately silences the hardware playback."""
        if self._current_proc is not None:
            try:
                self._current_proc.terminate()
                self._current_proc.wait(timeout=0.5)
            except Exception:
                try:
                    self._current_proc.kill()
                except Exception:
                    pass
            self._current_proc = None
        self._playing = False
        logger.info("Edge audio playback stopped.")


# Singleton instance for daemon
edge_player = EdgeAudioPlayer()
