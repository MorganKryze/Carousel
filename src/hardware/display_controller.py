from typing import Any, Optional

from loguru import logger

from core.config import Configuration
from core.system_state import SystemState
from display.custom_frames import CustomFrames


class DisplayController:
    """
    Singleton class to manage the RGB Matrix Display.
    """

    _instance: Optional["DisplayController"] = None

    SCREEN_RATIO: int = 16
    VALID_HARDWARE_MAPPINGS: tuple[str, ...] = ("regular", "adafruit-hat")

    def __new__(cls, use_emulator: bool = False) -> "DisplayController":
        if cls._instance is None:
            cls._instance = super(DisplayController, cls).__new__(cls)
            cls._instance._initialize(use_emulator=use_emulator)
        return cls._instance

    def _initialize(self, use_emulator: bool = False) -> None:
        """Initializes the display components."""
        self._config: Configuration = Configuration()
        self._state: SystemState = SystemState()

        self.led_rows: int = 0
        self.led_cols: int = 0
        self.disable_hardware_pulsing: bool = False
        self.hardware_mapping: str = ""
        self.target_fps: int = 0
        self.matrix: Any = None

        try:
            self._init_display_settings()
            self._init_matrix(use_emulator=use_emulator)
            CustomFrames.init(self.led_rows, self.led_cols)
            logger.info("Display system initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Display components: {e}")
            self._config.critical_exit(
                f"Failed to initialize display: {e}. Please check your configuration."
            )

    def _validate_dimension(self, value: int, name: str) -> None:
        """Validates that a dimension is a positive multiple of SCREEN_RATIO."""
        if value % self.SCREEN_RATIO != 0 or value <= 0:
            self._config.critical_exit(
                f"System.Matrix.{name} must be a positive multiple of {self.SCREEN_RATIO}."
            )

    def _init_display_settings(self) -> None:
        """Initializes the display settings from configuration."""
        self.led_rows = self._config.get("System", "Matrix", "led_rows", required=True)
        self._validate_dimension(self.led_rows, "led_rows")

        self.led_cols = self._config.get("System", "Matrix", "led_cols", required=True)
        self._validate_dimension(self.led_cols, "led_cols")

        brightness = self._config.get("System", "Matrix", "brightness", required=True)
        if (
            brightness < self._state.BRIGHTNESS_MIN
            or brightness > self._state.BRIGHTNESS_MAX
        ):
            self._config.critical_exit(
                f"System.Matrix.brightness must be between "
                f"{self._state.BRIGHTNESS_MIN} and {self._state.BRIGHTNESS_MAX}."
            )
        self._state.brightness = brightness

        self.disable_hardware_pulsing = self._config.get(
            "System", "Matrix", "disable_hardware_pulsing", required=True
        )
        if not isinstance(self.disable_hardware_pulsing, bool):
            self._config.critical_exit(
                "System.Matrix.disable_hardware_pulsing must be a boolean value."
            )

        self.hardware_mapping = self._config.get(
            "System", "Matrix", "hardware_mapping", required=True
        )
        if self.hardware_mapping not in self.VALID_HARDWARE_MAPPINGS:
            self._config.critical_exit(
                f"System.Matrix.hardware_mapping must be one of: "
                f"{', '.join(self.VALID_HARDWARE_MAPPINGS)}."
            )

        self.target_fps = self._config.get(
            "System", "Matrix", "target_fps", required=True
        )
        if self.target_fps <= 0:
            self._config.critical_exit(
                "System.Matrix.target_fps must be a positive integer."
            )

        logger.info("All display settings loaded.")

    def _init_matrix(self, use_emulator: bool = False) -> None:
        """Creates an RGBMatrix object with the specified parameters."""
        if use_emulator:
            from RGBMatrixEmulator import RGBMatrix  # type: ignore
            from RGBMatrixEmulator import RGBMatrixOptions

            logger.info("Using RGB Matrix Emulator.")
        else:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions  # type: ignore

            logger.info("Using hardware RGB Matrix.")

        logger.debug(
            f"Creating RGBMatrix options with height: {self.led_rows}, width: {self.led_cols}, "
            f"brightness: {self._state.brightness}, disable pulsing: {self.disable_hardware_pulsing}, "
            f"hardware mapping: {self.hardware_mapping}"
        )

        try:
            options = RGBMatrixOptions()
            options.rows = self.led_rows
            options.cols = self.led_cols
            options.brightness = self._state.brightness
            options.disable_hardware_pulsing = self.disable_hardware_pulsing
            options.hardware_mapping = self.hardware_mapping

            self.matrix = RGBMatrix(options=options)
            logger.debug("RGBMatrix object created successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to create RGBMatrix object: {e}") from e

    def update_brightness(self, brightness: int) -> None:
        """Updates the display brightness."""
        if (
            brightness < self._state.BRIGHTNESS_MIN
            or brightness > self._state.BRIGHTNESS_MAX
        ):
            logger.warning(
                f"Brightness {brightness} out of range "
                f"({self._state.BRIGHTNESS_MIN}-{self._state.BRIGHTNESS_MAX}). Ignoring."
            )
            return

        self._state.brightness = brightness
        if self.matrix:
            self.matrix.brightness = brightness
            logger.debug(f"Display brightness updated to {brightness}.")

    def cleanup(self) -> None:
        """Cleanup display resources on shutdown."""
        logger.info("Cleaning up DisplayController resources...")
        if self.matrix:
            try:
                self.matrix.Clear()
                logger.debug("Display cleared.")
            except Exception as e:
                logger.warning(f"Error clearing display: {e}")
