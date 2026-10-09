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
    host: str = Field(default="0.0.0.0", validation_alias="CRADLEECHO_HOST")
    port: int = Field(default=8000, validation_alias="CRADLEECHO_PORT")
    cors_origins: str = Field(default="*", validation_alias="CRADLEECHO_CORS_ORIGINS")
    min_brightness: float = Field(default=35.0, validation_alias="CRADLEECHO_MIN_BRIGHTNESS")

settings = Settings()
