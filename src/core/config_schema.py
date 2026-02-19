"""Pydantic models that define the configuration schema."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Metadata(BaseModel):
    """Metadata for configuration files."""

    model_config = ConfigDict(extra="forbid")

    id: int
    version: str
    created_at: str
    origin: str = "user"
    is_broken: bool = False
    broken_reason: Optional[str] = None

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


class SystemConfig(BaseModel):
    """System-level configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    Matrix: MatrixConfig
    Tilt_switch: TiltSwitchConfig = Field(alias="Tilt-switch")
    Encoder: EncoderConfig


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
