import sys
from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_default_presage_cmd() -> str:
    candidates = [
        Path(__file__).resolve().parent.parent / "presage_bridge" / "fake_bridge.py",
        Path("daemon/presage_bridge/fake_bridge.py"),
        Path("presage_bridge/fake_bridge.py"),
        Path("/opt/bridge/bridge"),
    ]
    for p in candidates:
        if p.exists():
            if p.suffix == ".py":
                return f"{sys.executable} {p}"
            return str(p)
    return f"{sys.executable} presage_bridge/fake_bridge.py"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    presage_api_key: SecretStr | None = Field(default=None, validation_alias="PRESAGE_API_KEY")
    
    camera: str = Field(default="0", validation_alias="CRADLEECHO_CAMERA")
    # Requested from the camera. Presage needs >= 25 fps; without an explicit request many UVC
    # cameras (e.g. Logitech Brio 101) fall back to a 15 fps default mode.
    camera_fps: float = Field(default=30.0, gt=0, validation_alias="CRADLEECHO_CAMERA_FPS")
    # Whether the camera starts on. It can be switched at runtime via POST /api/camera.
    camera_enabled: bool = Field(default=True, validation_alias="CRADLEECHO_CAMERA_ENABLED")
    source: str = Field(default="mock", validation_alias="CRADLEECHO_SOURCE")
    presage_cmd: str = Field(
        default_factory=_find_default_presage_cmd,
        validation_alias="CRADLEECHO_PRESAGE_CMD"
    )
    presage_fps: float = Field(default=30.0, gt=0, validation_alias="CRADLEECHO_PRESAGE_FPS")
    host: str = Field(default="0.0.0.0", validation_alias="CRADLEECHO_HOST")
    port: int = Field(default=8000, validation_alias="CRADLEECHO_PORT")
    cors_origins: str = Field(default="*", validation_alias="CRADLEECHO_CORS_ORIGINS")
    min_brightness: float = Field(default=35.0, validation_alias="CRADLEECHO_MIN_BRIGHTNESS")
    face_gate: bool = Field(default=True, validation_alias="CRADLEECHO_FACE_GATE")
    gate_chest_room: float = Field(default=1.75, gt=0, validation_alias="CRADLEECHO_GATE_CHEST_ROOM")
    gate_min_face_frac: float = Field(default=0.15, gt=0, validation_alias="CRADLEECHO_GATE_MIN_FACE")

    # Sleep-stage thresholds (see classifier.py). Motion is the camera frame-diff index (0..1):
    # ~0.00-0.05 for a still scene, ~0.3-0.5 when someone moves across the frame.
    asleep_brpm_min: float = Field(default=22.0, gt=0, validation_alias="CRADLEECHO_ASLEEP_BRPM_MIN")
    asleep_brpm_max: float = Field(default=40.0, gt=0, validation_alias="CRADLEECHO_ASLEEP_BRPM_MAX")
    calm_motion: float = Field(default=0.10, ge=0, validation_alias="CRADLEECHO_CALM_MOTION")
    restless_motion: float = Field(default=0.20, ge=0, validation_alias="CRADLEECHO_RESTLESS_MOTION")
    awake_motion: float = Field(default=0.45, ge=0, validation_alias="CRADLEECHO_AWAKE_MOTION")
    asleep_hold_s: float = Field(default=20.0, ge=0, validation_alias="CRADLEECHO_ASLEEP_HOLD_S")
    min_valid_brpm: float = Field(default=6.0, ge=0, validation_alias="CRADLEECHO_MIN_VALID_BRPM")


settings = Settings()
