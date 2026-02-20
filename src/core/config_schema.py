"""Pydantic models that define the configuration schema."""

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Metadata(BaseModel):
    """Metadata for configuration files."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=0)
    version: str
    created_at: str
    origin: Literal["author", "user"]
    is_broken: bool = False
    broken_reason: Optional[str] = None

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise ValueError("version must follow semantic format: X.Y.Z")
        return value

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError as error:
            raise ValueError("created_at must be in format YYYY-MM-DD HH:MM") from error
        return value

    @model_validator(mode="after")
    def validate_broken_consistency(self):
        reason = (self.broken_reason or "").strip()

        if self.is_broken and not reason:
            raise ValueError("broken_reason is required when is_broken is true")

        if not self.is_broken and reason:
            raise ValueError("broken_reason must be empty when is_broken is false")

        self.broken_reason = reason or None
        return self


class MatrixConfig(BaseModel):
    """LED matrix hardware configuration."""

    model_config = ConfigDict(extra="forbid")

    led_rows: int
    led_cols: int
    brightness: int
    disable_hardware_pulsing: bool
    hardware_mapping: str
    target_fps: int


class TiltSwitchConfig(BaseModel):
    """Tilt switch GPIO configuration."""

    model_config = ConfigDict(extra="forbid")

    gpio: int
    bounce_time: float


class EncoderConfig(BaseModel):
    """Encoder GPIO configuration."""

    model_config = ConfigDict(extra="forbid")

    gpio_clk: int
    gpio_dt: int
    gpio_sw: int
    bounce_time: float
    double_press_window: float
    long_press_window: float
    natural_rotation: bool


class NetworkConfig(BaseModel):
    """Network configuration for WiFi and recovery hotspot fallback."""

    model_config = ConfigDict(extra="forbid")

    ssid: Optional[str] = None
    password: Optional[str] = None
    wpa_level: Literal[0, 1, 2] = 0
    hotspot_ssid: str = Field(default="Carousel", min_length=1)
    hotspot_password: Optional[str] = None
    max_attempts: int = Field(default=3, ge=1)
    interface: str = Field(default="wlan0", min_length=1)

    @field_validator("ssid", "password", "hotspot_password", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_hotspot_security(self):
        if self.wpa_level > 0:
            if not self.hotspot_password:
                raise ValueError(
                    "hotspot_password is required when wpa_level is 1 or 2"
                )
            if len(self.hotspot_password) < 8:
                raise ValueError(
                    "hotspot_password must be at least 8 characters when wpa_level is 1 or 2"
                )
        return self


class SystemConfig(BaseModel):
    """System-level configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    Matrix: MatrixConfig
    Tilt_switch: TiltSwitchConfig = Field(alias="Tilt-switch")
    Encoder: EncoderConfig
    Network: NetworkConfig = Field(default_factory=NetworkConfig)


class ModuleMeta(BaseModel):
    """Module metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class ModuleConfig(BaseModel):
    """Module configuration entry."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    meta: ModuleMeta
    config: Optional[Dict[str, Any]] = None


class AppMeta(BaseModel):
    """Application metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    provides_horizontal_content: bool
    provides_vertical_content: bool


class AppConfig(BaseModel):
    """Application configuration entry."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    order: int
    meta: AppMeta
    config: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[str]] = None


class ConfigRoot(BaseModel):
    """Top-level configuration schema."""

    model_config = ConfigDict(extra="forbid")

    Metadata: Metadata
    System: SystemConfig
    Modules: Dict[str, ModuleConfig] = {}
    Apps: Dict[str, AppConfig] = {}
