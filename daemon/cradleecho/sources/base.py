"""Base protocol and data models for vitals sources."""

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class Reading:
    """Biometric reading from a sensor or mock generator."""
    brpm: float
    bpm: float
    confidence: float
    motion_index: Optional[float] = None
    timestamp: Optional[float] = None


@runtime_checkable
class VitalsSource(Protocol):
    """Protocol implemented by vitals telemetry sources."""

    async def start(self) -> None:
        """Start background workers or subprocesses if any."""
        ...

    async def stop(self) -> None:
        """Stop background workers and clean up resources."""
        ...

    def read(self) -> Reading:
        """Fetch the most recent biometric reading."""
        ...

    def set_forced_mode(self, mode: Optional[str]) -> None:
        """Set an operational override (e.g., 'RESTLESS' or None)."""
        ...
