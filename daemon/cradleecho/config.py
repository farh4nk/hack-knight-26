import sys

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    presage_api_key: SecretStr | None = Field(default=None, validation_alias="PRESAGE_API_KEY")
    
    camera: str = Field(default="0", validation_alias="CRADLEECHO_CAMERA")
    source: str = Field(default="mock", validation_alias="CRADLEECHO_SOURCE")
    presage_cmd: str = Field(
        default=f"{sys.executable} presage_bridge/fake_bridge.py",
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

    # Two-way audio
    listen_enabled: bool = Field(default=False, validation_alias="CRADLEECHO_LISTEN")
    mic_device: str = Field(default="default", validation_alias="CRADLEECHO_MIC")

    # Night vision
    night_vision_mode: str = Field(default="AUTO", validation_alias="CRADLEECHO_NIGHT_VISION")
    night_on_below: float = Field(default=60.0, validation_alias="CRADLEECHO_NIGHT_ON_BELOW")
    night_off_above: float = Field(default=80.0, validation_alias="CRADLEECHO_NIGHT_OFF_ABOVE")


settings = Settings()
