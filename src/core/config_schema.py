"""Pydantic models that define the configuration schema."""

import re
from datetime import datetime
from typing import Any, Dict, Literal, Optional

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

    led_rows: int = Field(ge=16)
    led_cols: int = Field(ge=16)
    brightness: int = Field(ge=0, le=100)
    disable_hardware_pulsing: bool
    hardware_mapping: Literal["regular", "adafruit-hat"]
    target_fps: int = Field(ge=1)

    @field_validator("led_rows", "led_cols")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        if value % 16 != 0:
            raise ValueError("must be a positive multiple of 16")
        return value


class TiltSwitchConfig(BaseModel):
    """Tilt switch GPIO configuration."""

    model_config = ConfigDict(extra="forbid")

    gpio: int = Field(ge=0, le=27)
    bounce_time: float = Field(ge=0)


class EncoderConfig(BaseModel):
    """Encoder GPIO configuration."""

    model_config = ConfigDict(extra="forbid")

    gpio_clk: int = Field(ge=0, le=27)
    gpio_dt: int = Field(ge=0, le=27)
    gpio_sw: int = Field(ge=0, le=27)
    bounce_time: float = Field(ge=0)
    double_press_window: float = Field(gt=0)
    long_press_window: float = Field(gt=0)
    natural_rotation: bool

    @model_validator(mode="after")
    def validate_encoder_gpio_uniqueness(self):
        gpio_values = {self.gpio_clk, self.gpio_dt, self.gpio_sw}
        if len(gpio_values) != 3:
            raise ValueError("Encoder GPIO pins must be distinct")
        return self


class NetworkConfig(BaseModel):
    """Network configuration for WiFi and recovery hotspot fallback."""

    model_config = ConfigDict(extra="forbid")

    ssid: Optional[str] = None
    password: Optional[str] = None
    wpa_level: Literal[0, 1, 2] = 0
    hotspot_ssid: str = Field(default="Carousel", min_length=1, max_length=32)
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

    @field_validator("hotspot_ssid", "interface", mode="before")
    @classmethod
    def normalize_required_strings(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip()

    @model_validator(mode="after")
    def validate_hotspot_security(self):
        if bool(self.ssid) != bool(self.password):
            raise ValueError("ssid and password must both be set or both be empty")

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

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_strings(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip()


class ModuleConfig(BaseModel):
    """Module configuration entry."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    meta: ModuleMeta
    config: Optional[Dict[str, Any]] = None


class AppConfig(BaseModel):
    """Application configuration entry.

    Metadata (name, description, orientations) and dependencies have been moved
    to ``src/core/app_catalog.py``.  This model now covers only user-editable
    fields: enabled state, carousel order, and per-app config dict.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    order: int = Field(ge=1)
    config: Optional[Dict[str, Any]] = None


class ConfigRoot(BaseModel):
    """Top-level configuration schema."""

    model_config = ConfigDict(extra="forbid")

    Metadata: Metadata
    System: SystemConfig
    Modules: Dict[str, ModuleConfig] = Field(default_factory=dict)
    Apps: Dict[str, AppConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_root_consistency(self):
        for module_key in self.Modules:
            if not module_key.strip():
                raise ValueError("Modules cannot contain empty names")

        app_order_map: Dict[int, str] = {}
        for app_key, app_config in self.Apps.items():
            if not app_key.strip():
                raise ValueError("Apps cannot contain empty names")

            if app_config.order in app_order_map:
                raise ValueError(
                    f"Duplicate app order detected: {app_config.order} "
                    f"({app_order_map[app_config.order]} and {app_key})"
                )
            app_order_map[app_config.order] = app_key

        return self
